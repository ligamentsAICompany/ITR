"""Deterministic filing package generation service."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.models.decision import ITRDecisionResponse
from app.models.document import PublicDocumentMetadata
from app.models.filing_package import (
    FilingPackage,
    FilingPackageArtifact,
    FilingPackageArtifactType,
    FilingPackageExplanation,
    FilingPackageStatus,
    FilingPackageWarning,
)
from app.models.tax_computation import TaxComputationResult
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport, ValidationStatus, mask_sensitive
from app.repositories.filing_package_repository import FilingPackageRepository
from app.services.draft_itr_mapper import OFFICIAL_SCHEMA_WARNING, PACKAGE_VERSION
from app.services.draft_itr_payload_service import DraftItrPayloadService
from app.services.filing_package_artifact_service import FilingPackageArtifactService


class FilingPackageService:
    def __init__(
        self,
        *,
        repository: FilingPackageRepository | None = None,
        draft_payload_service: DraftItrPayloadService | None = None,
        artifact_service: FilingPackageArtifactService | None = None,
    ) -> None:
        self.repository = repository or FilingPackageRepository()
        self.draft_payload_service = draft_payload_service or DraftItrPayloadService()
        self.artifact_service = artifact_service or FilingPackageArtifactService()

    def generate(
        self,
        *,
        profile: CanonicalTaxProfile | dict[str, Any],
        candidate_itr: ITRDecisionResponse,
        validation_report: ValidationReport,
        tax_computation_result: TaxComputationResult,
        documents: list[PublicDocumentMetadata],
        extracted_evidence_summary: dict[str, Any] | None = None,
        owner_user_id: str | None = None,
        organization_id: str | None = None,
        created_by: str | None = None,
    ) -> FilingPackage:
        profile_copy = CanonicalTaxProfile.model_validate(deepcopy(profile))
        warnings = self._warnings(validation_report, tax_computation_result)
        status = deterministic_status(validation_report, tax_computation_result)
        readiness_score = deterministic_readiness_score(validation_report, tax_computation_result, status)
        package = FilingPackage(
            owner_user_id=owner_user_id,
            organization_id=organization_id,
            created_by=created_by,
            assessment_year=profile_copy.assessment_year,
            previous_year=profile_copy.previous_year,
            candidate_itr=candidate_itr.candidate_itr,
            status=status,
            readiness_score=readiness_score,
            validation_run_id=validation_report.validation_run_id,
            computation_id=tax_computation_result.computation_id,
            document_ids=[document.document_id for document in documents],
            warnings=warnings,
        )

        draft_payload = self.draft_payload_service.generate(
            candidate_itr=candidate_itr,
            profile=profile_copy,
            validation_report=validation_report,
            tax_computation_result=tax_computation_result,
        )
        artifacts = self._build_artifacts(
            package=package,
            validation_report=validation_report,
            tax_computation_result=tax_computation_result,
            draft_payload=draft_payload,
            documents=documents,
            extracted_evidence_summary=extracted_evidence_summary or {},
        )
        package.artifacts = [artifact for artifact, _content in artifacts]
        package.updated_at = datetime.now(UTC)
        self.repository.save(package)
        for artifact, content in artifacts:
            self.repository.save_artifact_content(package.package_id, artifact.artifact_id, content)
        return package

    def get(self, package_id: str) -> FilingPackage | None:
        return self.repository.get(package_id)

    def get_artifact_content(self, package_id: str, artifact_id: str) -> bytes | None:
        package = self.repository.get(package_id)
        if package is None or not any(artifact.artifact_id == artifact_id for artifact in package.artifacts):
            return None
        return self.repository.get_artifact_content(package_id, artifact_id)

    def explain(self, package: FilingPackage) -> FilingPackageExplanation:
        artifact_names = ", ".join(artifact.filename for artifact in package.artifacts)
        explanation = (
            f"This is a draft filing package for {package.candidate_itr} with status "
            f"{package.status.replace('_', ' ')} and readiness score {package.readiness_score}. "
            f"It includes these generated review artifacts: {artifact_names}. "
            "It is not submitted to the Income Tax Department and is not an official government filing."
        )
        return FilingPackageExplanation(
            package_id=package.package_id,
            explanation=explanation,
            grounded_artifact_ids=[artifact.artifact_id for artifact in package.artifacts],
        )

    def _warnings(
        self,
        validation_report: ValidationReport,
        tax_computation_result: TaxComputationResult,
    ) -> list[FilingPackageWarning]:
        warnings = [
            FilingPackageWarning(
                severity="medium",
                message=OFFICIAL_SCHEMA_WARNING,
                source="draft_itr_payload",
                recommendation="Review the draft package with a qualified tax professional before any filing action.",
            )
        ]
        if validation_report.overall_status == ValidationStatus.FAILED:
            warnings.append(
                FilingPackageWarning(
                    severity="critical",
                    message="Validation failed. The package is blocked until deterministic validation issues are resolved.",
                    source="validation_report",
                    recommendation="Resolve validation issues before preparing export-ready filing data.",
                )
            )
        elif validation_report.overall_status in {ValidationStatus.NEEDS_REVIEW, ValidationStatus.WARNING}:
            warnings.append(
                FilingPackageWarning(
                    severity="high",
                    message="Validation requires review before this draft package can be relied on.",
                    source="validation_report",
                    recommendation="Review the validation report and supporting evidence.",
                )
            )
        for warning in tax_computation_result.warnings:
            warnings.append(
                FilingPackageWarning(
                    severity="medium",
                    message=warning.message,
                    source=f"tax_computation:{warning.code}",
                    recommendation="Review the deterministic tax computation warning.",
                )
            )
        if tax_computation_result.is_preview:
            warnings.append(
                FilingPackageWarning(
                    severity="high",
                    message="Tax computation is marked preview and must be reviewed before package use.",
                    source="tax_computation",
                    recommendation="Resolve upstream validation or data issues, then recompute tax.",
                )
            )
        return warnings

    def _build_artifacts(
        self,
        *,
        package: FilingPackage,
        validation_report: ValidationReport,
        tax_computation_result: TaxComputationResult,
        draft_payload: dict[str, Any],
        documents: list[PublicDocumentMetadata],
        extracted_evidence_summary: dict[str, Any],
    ) -> list[tuple[FilingPackageArtifact, bytes]]:
        manifest = {
            "package_id": package.package_id,
            "package_version": PACKAGE_VERSION,
            "status": package.status,
            "candidate_itr": package.candidate_itr,
            "assessment_year": package.assessment_year,
            "previous_year": package.previous_year,
            "validation_run_id": package.validation_run_id,
            "computation_id": package.computation_id,
            "artifact_count": 5,
            "disclaimer": "Draft internal package only. Not submitted to the Income Tax Department.",
        }
        filing_summary = mask_sensitive(
            {
                "package_id": package.package_id,
                "status": package.status,
                "readiness_score": package.readiness_score,
                "candidate_itr": package.candidate_itr,
                "document_summary": [
                    {
                        "document_id": document.document_id,
                        "document_type": document.document_type,
                        "size": document.size,
                        "mime_type": document.mime_type,
                        "sha256": document.sha256,
                        "status": document.status,
                    }
                    for document in documents
                ],
                "evidence_summary": extracted_evidence_summary,
                "warnings": [warning.model_dump(mode="json") for warning in package.warnings],
            }
        )
        validation_payload = validation_report.model_dump(mode="json")
        tax_payload = tax_computation_result.model_dump(mode="json")
        specs = [
            (FilingPackageArtifactType.PACKAGE_MANIFEST, "package_manifest.json", manifest),
            (FilingPackageArtifactType.FILING_SUMMARY_JSON, "filing_summary.json", filing_summary),
            (FilingPackageArtifactType.VALIDATION_REPORT_JSON, "validation_report.json", validation_payload),
            (FilingPackageArtifactType.TAX_COMPUTATION_REPORT, "tax_computation_report.json", tax_payload),
            (FilingPackageArtifactType.DRAFT_ITR_PAYLOAD, "draft_itr_payload.json", draft_payload),
        ]
        return [
            self.artifact_service.build_json_artifact(
                artifact_type=artifact_type,
                filename=filename,
                payload=payload,
            )
            for artifact_type, filename, payload in specs
        ]


def deterministic_status(
    validation_report: ValidationReport,
    tax_computation_result: TaxComputationResult,
) -> FilingPackageStatus:
    if validation_report.overall_status == ValidationStatus.FAILED:
        return FilingPackageStatus.BLOCKED
    if validation_report.overall_status in {ValidationStatus.NEEDS_REVIEW, ValidationStatus.WARNING}:
        return FilingPackageStatus.NEEDS_REVIEW
    if tax_computation_result.is_preview or tax_computation_result.warnings:
        return FilingPackageStatus.NEEDS_REVIEW
    return FilingPackageStatus.READY_FOR_CA_REVIEW


def deterministic_readiness_score(
    validation_report: ValidationReport,
    tax_computation_result: TaxComputationResult,
    status: FilingPackageStatus,
) -> int:
    score = min(validation_report.readiness_score, 90)
    if status == FilingPackageStatus.BLOCKED:
        return min(score, 40)
    if status == FilingPackageStatus.NEEDS_REVIEW:
        score = min(score, 75)
    if tax_computation_result.is_preview:
        score = min(score, 70)
    if tax_computation_result.warnings:
        score = min(score, 80)
    return max(score, 0)

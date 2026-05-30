"""Deterministic official schema export generation service."""

from copy import deepcopy
from datetime import UTC, datetime

from app.models.decision import ITRDecisionResponse
from app.models.filing_package import FilingPackage
from app.models.itr_export import (
    ItrExport,
    ItrExportExplanation,
    ItrExportStatus,
    OfficialSchemaValidationResult,
    OfficialSchemaValidationStatus,
)
from app.models.tax_computation import TaxComputationResult
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport
from app.repositories.itr_export_repository import ItrExportRepository
from app.services.itr_export_artifact_service import ItrExportArtifactService
from app.services.itr_export_mapper import mapper_for_itr
from app.services.official_schema_validation_service import OfficialSchemaValidationService
from app.services.schema_pack_service import SchemaPackService


class ItrExportService:
    def __init__(
        self,
        *,
        repository: ItrExportRepository | None = None,
        schema_pack_service: SchemaPackService | None = None,
        validation_service: OfficialSchemaValidationService | None = None,
        artifact_service: ItrExportArtifactService | None = None,
    ) -> None:
        self.repository = repository or ItrExportRepository()
        self.schema_pack_service = schema_pack_service or SchemaPackService()
        self.validation_service = validation_service or OfficialSchemaValidationService()
        self.artifact_service = artifact_service or ItrExportArtifactService()

    def generate(
        self,
        *,
        profile: CanonicalTaxProfile | dict,
        candidate_itr: ITRDecisionResponse,
        validation_report: ValidationReport,
        tax_computation_result: TaxComputationResult,
        package: FilingPackage | None = None,
        owner_user_id: str | None = None,
        organization_id: str | None = None,
        created_by: str | None = None,
    ) -> ItrExport:
        profile_copy = CanonicalTaxProfile.model_validate(deepcopy(profile))
        active = self.schema_pack_service.active_for(
            assessment_year=profile_copy.assessment_year,
            itr_form=candidate_itr.candidate_itr,
        )
        if active is None:
            result = self.validation_service.not_configured(
                candidate_itr=candidate_itr.candidate_itr,
                assessment_year=profile_copy.assessment_year,
            )
            export = self._export(
                profile=profile_copy,
                candidate_itr=candidate_itr,
                package=package,
                owner_user_id=owner_user_id,
                organization_id=organization_id,
                created_by=created_by,
                status=ItrExportStatus.NOT_CONFIGURED,
                validation_result=result,
            )
            return self.repository.save(export)

        schema_pack, schema = active
        mapper = mapper_for_itr(candidate_itr.candidate_itr)
        mapping = mapper.map(
            profile=profile_copy,
            candidate_itr=candidate_itr,
            validation_report=validation_report,
            tax_computation_result=tax_computation_result,
            schema=schema,
        )
        if mapping.errors:
            result = self.validation_service.mapping_failed(
                schema_pack=schema_pack,
                candidate_itr=candidate_itr.candidate_itr,
                assessment_year=profile_copy.assessment_year,
                errors=[error.model_dump(mode="json") for error in mapping.errors],
                warnings=[warning.model_dump(mode="json") for warning in mapping.warnings],
            )
            export = self._export(
                profile=profile_copy,
                candidate_itr=candidate_itr,
                package=package,
                owner_user_id=owner_user_id,
                organization_id=organization_id,
                created_by=created_by,
                status=ItrExportStatus.BLOCKED,
                validation_result=result,
                schema_pack_id=schema_pack.schema_pack_id,
                warnings=[warning.message for warning in mapping.warnings],
            )
            return self.repository.save(export)

        result = self.validation_service.validate(
            schema_pack=schema_pack,
            schema=schema,
            payload=mapping.payload,
            candidate_itr=candidate_itr.candidate_itr,
            assessment_year=profile_copy.assessment_year,
        )
        status = export_status_for(result)
        export = self._export(
            profile=profile_copy,
            candidate_itr=candidate_itr,
            package=package,
            owner_user_id=owner_user_id,
            organization_id=organization_id,
            created_by=created_by,
            status=status,
            validation_result=result,
            schema_pack_id=schema_pack.schema_pack_id,
            warnings=[warning.message for warning in mapping.warnings],
        )
        if status == ItrExportStatus.READY_FOR_DOWNLOAD:
            artifact, content = self.artifact_service.build_json_artifact(
                export_id=export.export_id,
                candidate_itr=candidate_itr.candidate_itr,
                payload=mapping.payload,
            )
            export.artifacts = [artifact]
            export.updated_at = datetime.now(UTC)
            self.repository.save(export)
            self.repository.save_artifact_content(export.export_id, artifact.artifact_id, content)
            return export
        return self.repository.save(export)

    def validate_only(
        self,
        *,
        profile: CanonicalTaxProfile,
        candidate_itr: ITRDecisionResponse,
        validation_report: ValidationReport,
        tax_computation_result: TaxComputationResult,
    ) -> OfficialSchemaValidationResult:
        export = self.generate(
            profile=profile,
            candidate_itr=candidate_itr,
            validation_report=validation_report,
            tax_computation_result=tax_computation_result,
        )
        return export.validation_result

    def get(self, export_id: str) -> ItrExport | None:
        return self.repository.get(export_id)

    def get_artifact_content(self, export_id: str, artifact_id: str) -> bytes | None:
        export = self.repository.get(export_id)
        if export is None or not any(artifact.artifact_id == artifact_id for artifact in export.artifacts):
            return None
        return self.repository.get_artifact_content(export_id, artifact_id)

    def explain(self, export: ItrExport) -> ItrExportExplanation:
        result = export.validation_result
        if result.status == OfficialSchemaValidationStatus.PASSED:
            text = "Schema validation passed against the configured schema pack. This only confirms payload structure."
        elif result.status == OfficialSchemaValidationStatus.NOT_CONFIGURED:
            text = "No active schema pack is configured, so export validation cannot run."
        else:
            count = len(result.errors)
            text = f"Schema validation found {count} deterministic issue(s). Review the listed fields and regenerate the export."
        return ItrExportExplanation(
            export_id=export.export_id,
            validation_id=result.validation_id,
            explanation=text,
            grounded_error_codes=[error.code for error in result.errors],
        )

    def _export(
        self,
        *,
        profile: CanonicalTaxProfile,
        candidate_itr: ITRDecisionResponse,
        package: FilingPackage | None,
        owner_user_id: str | None,
        organization_id: str | None,
        created_by: str | None,
        status: ItrExportStatus,
        validation_result: OfficialSchemaValidationResult,
        schema_pack_id: str | None = None,
        warnings: list[str] | None = None,
    ) -> ItrExport:
        return ItrExport(
            package_id=package.package_id if package else None,
            owner_user_id=owner_user_id or (package.owner_user_id if package else None),
            organization_id=organization_id or (package.organization_id if package else None),
            created_by=created_by or (package.created_by if package else None),
            assessment_year=profile.assessment_year,
            previous_year=profile.previous_year,
            candidate_itr=candidate_itr.candidate_itr,
            schema_pack_id=schema_pack_id,
            status=status,
            validation_result=validation_result,
            warnings=warnings or [],
        )


def export_status_for(result: OfficialSchemaValidationResult) -> ItrExportStatus:
    if result.status == OfficialSchemaValidationStatus.NOT_CONFIGURED:
        return ItrExportStatus.NOT_CONFIGURED
    if result.status == OfficialSchemaValidationStatus.PASSED:
        return ItrExportStatus.READY_FOR_DOWNLOAD
    if result.status == OfficialSchemaValidationStatus.NEEDS_REVIEW:
        return ItrExportStatus.BLOCKED
    return ItrExportStatus.SCHEMA_FAILED

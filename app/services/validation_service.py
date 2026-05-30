"""Validation orchestration for Phase 2 readiness reports."""

from uuid import uuid4

from app.models.document import ExtractionResult, PublicDocumentMetadata
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import (
    ValidationEvidenceSummary,
    ValidationReport,
)
from app.services.reconciliation_service import ReconciliationService
from app.services.validation_rules import (
    approved_extracted_fields,
    compute_overall_status,
    compute_readiness_score,
    run_profile_rules,
)


class ValidationService:
    def __init__(self, reconciliation_service: ReconciliationService | None = None) -> None:
        self.reconciliation_service = reconciliation_service or ReconciliationService()

    def run(
        self,
        *,
        profile: CanonicalTaxProfile,
        documents: list[PublicDocumentMetadata],
        extractions: list[ExtractionResult],
        approved_field_ids: list[str],
        profile_id: str | None = None,
        session_id: str | None = None,
    ) -> ValidationReport:
        approved_fields = approved_extracted_fields(extractions, approved_field_ids)
        profile_issues, missing_fields = run_profile_rules(
            profile=profile,
            documents=documents,
            approved_fields=approved_fields,
        )
        reconciliation_issues, conflicts, approved_count = self.reconciliation_service.reconcile(
            profile=profile,
            extractions=extractions,
            approved_field_ids=approved_field_ids,
        )
        issues = [*profile_issues, *reconciliation_issues]
        warnings = [issue.message for issue in issues if issue.severity in {"medium", "low"}]
        if not documents:
            warnings.insert(
                0,
                "No documents uploaded; validation is limited to manual entries and does not block filing unless a critical issue exists.",
            )
        evidence_summary = ValidationEvidenceSummary(
            document_count=len(documents),
            approved_extracted_field_count=approved_count,
            document_types=sorted({str(document.document_type) for document in documents}),
        )
        return ValidationReport(
            validation_run_id=f"val-{uuid4()}",
            profile_id=profile_id,
            session_id=session_id,
            overall_status=compute_overall_status(issues),
            readiness_score=compute_readiness_score(issues),
            issues=issues,
            missing_fields=missing_fields,
            conflicts=conflicts,
            warnings=warnings,
            evidence_summary=evidence_summary,
        )

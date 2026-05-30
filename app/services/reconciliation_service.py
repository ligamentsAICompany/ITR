"""Evidence reconciliation between canonical profile and approved extractions."""

from app.models.document import ExtractionResult
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ReconciliationConflict, ValidationIssue
from app.services.validation_rules import approved_extracted_fields, compare_approved_fields


class ReconciliationService:
    """Compare user-approved evidence with the canonical profile without mutating either."""

    def reconcile(
        self,
        *,
        profile: CanonicalTaxProfile,
        extractions: list[ExtractionResult],
        approved_field_ids: list[str],
    ) -> tuple[list[ValidationIssue], list[ReconciliationConflict], int]:
        approved_fields = approved_extracted_fields(extractions, approved_field_ids)
        issues, conflicts = compare_approved_fields(profile=profile, approved_fields=approved_fields)
        return issues, conflicts, len(approved_fields)

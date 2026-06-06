"""Map deterministic outputs into an internal draft ITR payload.

This mapper does not create official ITR JSON and does not invent schedules. It
only repackages canonical profile summaries, validation status, and computed tax
numbers for human/CA review.
"""

from typing import Any

from app.models.decision import ITRDecisionResponse
from app.models.tax_computation import TaxComputationResult
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport, mask_sensitive

PACKAGE_VERSION = "filing-package/v0.1"
SCHEMA_STATUS = "internal_draft_not_official"
OFFICIAL_SCHEMA_WARNING = "Official ITR schema validation is not yet implemented for this package."


class DraftItrMapper:
    def map(
        self,
        *,
        candidate_itr: ITRDecisionResponse,
        profile: CanonicalTaxProfile,
        validation_report: ValidationReport,
        tax_computation_result: TaxComputationResult,
    ) -> dict[str, Any]:
        warnings = [OFFICIAL_SCHEMA_WARNING]
        warnings.extend(validation_report.warnings)
        warnings.extend(warning.message for warning in tax_computation_result.warnings)
        if profile.income_heads.capital_gains.has_income == "yes":
            warnings.append("Capital gains schedule details are not mapped to an official ITR schedule in this draft.")
        if profile.foreign_assets.has_foreign_assets == "yes" or profile.foreign_assets.has_foreign_income == "yes":
            warnings.append("Foreign asset/income schedule details are not mapped to an official ITR schedule in this draft.")

        return mask_sensitive(
            {
                "payload_type": "draft_itr_payload",
                "schema_status": SCHEMA_STATUS,
                "candidate_itr": candidate_itr.candidate_itr,
                "assessment_year": profile.assessment_year,
                "previous_year": profile.previous_year,
                "taxpayer": {
                    "full_name": profile.taxpayer_master.full_name,
                    "entity_type": profile.entity_type,
                    "residency_status": profile.residency_status.status,
                    "aadhaar_last4": profile.user_identity.aadhaar_last4,
                },
                "income_summary": tax_computation_result.income.model_dump(mode="json"),
                "deductions": tax_computation_result.deductions.model_dump(mode="json"),
                "tax_computation": {
                    "selected_regime": tax_computation_result.selected_regime,
                    "taxable_income": tax_computation_result.taxable_income,
                    "tax_before_rebate": tax_computation_result.tax_before_rebate,
                    "rebate": tax_computation_result.rebate,
                    "surcharge": tax_computation_result.surcharge,
                    "cess": tax_computation_result.cess,
                    "total_tax_liability": tax_computation_result.total_tax_liability,
                    "refund_due": tax_computation_result.refund_due,
                    "tax_payable": tax_computation_result.tax_payable,
                },
                "tax_credits": tax_computation_result.credits.model_dump(mode="json"),
                "validation": {
                    "validation_run_id": validation_report.validation_run_id,
                    "overall_status": validation_report.overall_status,
                    "readiness_score": validation_report.readiness_score,
                    "issue_count": len(validation_report.issues),
                },
                "warnings": sorted(set(warnings)),
                "package_version": PACKAGE_VERSION,
            }
        )

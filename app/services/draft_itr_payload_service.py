"""Service facade for internal draft ITR payload generation."""

from typing import Any

from app.models.decision import ITRDecisionResponse
from app.models.tax_computation import TaxComputationResult
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport
from app.services.draft_itr_mapper import DraftItrMapper


class DraftItrPayloadService:
    def __init__(self, mapper: DraftItrMapper | None = None) -> None:
        self.mapper = mapper or DraftItrMapper()

    def generate(
        self,
        *,
        candidate_itr: ITRDecisionResponse,
        profile: CanonicalTaxProfile,
        validation_report: ValidationReport,
        tax_computation_result: TaxComputationResult,
    ) -> dict[str, Any]:
        return self.mapper.map(
            candidate_itr=candidate_itr,
            profile=profile,
            validation_report=validation_report,
            tax_computation_result=tax_computation_result,
        )

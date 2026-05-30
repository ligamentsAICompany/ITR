"""Thin agent facade for deterministic tax computation.

The agent delegates all math to TaxComputationService. It may explain a stored
result, but it never computes tax, changes ITR decisions, or creates filing JSON.
"""

from app.models.decision import ITRDecisionResponse
from app.models.tax_computation import TaxComputationResult, TaxExplanationResponse, TaxRegime
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport
from app.services.tax_computation_service import TaxComputationService


class TaxComputationAgent:
    def __init__(self, service: TaxComputationService | None = None) -> None:
        self.service = service or TaxComputationService()

    def run(
        self,
        *,
        profile: CanonicalTaxProfile,
        candidate_itr: ITRDecisionResponse,
        validation_report: ValidationReport | None = None,
        selected_regime: TaxRegime | None = None,
    ) -> TaxComputationResult:
        return self.service.compute(
            profile=profile,
            candidate_itr=candidate_itr,
            validation_report=validation_report,
            selected_regime=selected_regime,
        )

    def explain(self, result: TaxComputationResult) -> TaxExplanationResponse:
        return self.service.explain(result)

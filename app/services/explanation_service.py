"""Explanation service backed by the constrained SLM facade."""

from app.models.decision import ExplanationResponse, ITRDecisionResponse
from app.services.slm_service import get_default_slm_service


def explain_decision(decision: ITRDecisionResponse) -> ExplanationResponse:
    slm_service = get_default_slm_service()
    explanation = slm_service.generate_explanation(
        candidate_itr=decision.candidate_itr,
        reason_codes=decision.reason_codes,
        missing_fields=decision.missing_fields,
    )
    return ExplanationResponse(
        candidate_itr=decision.candidate_itr,
        explanation=explanation,
        reason_codes=decision.reason_codes,
        missing_fields=decision.missing_fields,
        confidence=decision.confidence,
    )

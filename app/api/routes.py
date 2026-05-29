"""API endpoints for deterministic ITR classification."""

from typing import Any

from fastapi import APIRouter

from app.models.decision import (
    ClarificationRequest,
    ClarificationResponse,
    ExplanationResponse,
    ITRDecisionResponse,
    MissingFieldsResponse,
)
from app.models.tax_profile import CanonicalTaxProfile
from app.services.explanation_service import explain_decision
from app.services.itr_service import get_missing_fields, run_itr_decision
from app.services.normalization_service import normalize_raw_user_data
from app.services.slm_service import get_default_slm_service

router = APIRouter()


@router.post("/normalize", response_model=CanonicalTaxProfile)
def normalize(raw_user_data: dict[str, Any]) -> CanonicalTaxProfile:
    return normalize_raw_user_data(raw_user_data)


@router.post("/itr-decision", response_model=ITRDecisionResponse)
def itr_decision(profile: CanonicalTaxProfile) -> ITRDecisionResponse:
    return run_itr_decision(profile)


@router.post("/missing-fields", response_model=MissingFieldsResponse)
def missing_fields(profile: CanonicalTaxProfile) -> MissingFieldsResponse:
    return get_missing_fields(profile)


@router.post("/explain", response_model=ExplanationResponse)
def explain(decision: ITRDecisionResponse) -> ExplanationResponse:
    return explain_decision(decision)


@router.post("/clarify", response_model=ClarificationResponse)
def clarify(request: ClarificationRequest) -> ClarificationResponse:
    slm_service = get_default_slm_service()
    question = slm_service.generate_clarification_question(
        missing_fields=request.missing_fields,
        context=request.context,
    )
    return ClarificationResponse(question=question)

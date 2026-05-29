"""Service wrapper around the existing deterministic ITR engine."""

from itr_engine import classify_itr

from app.models.decision import ITRDecisionResponse, MissingFieldsResponse
from app.models.tax_profile import CanonicalTaxProfile


def run_itr_decision(profile: CanonicalTaxProfile) -> ITRDecisionResponse:
    result = classify_itr(profile.model_dump(exclude_none=True))
    return ITRDecisionResponse.model_validate(result)


def get_missing_fields(profile: CanonicalTaxProfile) -> MissingFieldsResponse:
    decision = run_itr_decision(profile)
    return MissingFieldsResponse(missing_fields=decision.missing_fields)

"""Rule-based normalization service for partial raw user data."""

from typing import Any

from app.core.errors import InvalidSchemaError
from app.models.tax_profile import CanonicalTaxProfile


def normalize_raw_user_data(raw_data: dict[str, Any]) -> CanonicalTaxProfile:
    """Normalize partial raw input into a canonical profile.

    This is intentionally deterministic and simple. It only maps known fields
    and fills unknowns so the rules engine can report missing/ambiguous items.
    """
    salary_income = _number(raw_data.get("salary_income", 0), ("salary_income",))
    ltcg_112a_amount = _number(raw_data.get("ltcg_112a_amount", 0), ("ltcg_112a_amount",))
    capital_gains_income = _number(
        raw_data.get("capital_gains_income", ltcg_112a_amount),
        ("capital_gains_income",),
    )
    business_income = _number(
        raw_data.get("business_profession_income", 0),
        ("business_profession_income",),
    )
    other_income = _number(raw_data.get("other_sources_income", 0), ("other_sources_income",))
    house_property_income = _number(
        raw_data.get("house_property_income", 0),
        ("house_property_income",),
    )

    profile = {
        "schema_version": "canonical-tax-profile/v0.1",
        "assessment_year": raw_data.get("assessment_year", "2026-27"),
        "previous_year": raw_data.get("previous_year"),
        "return_filing_reason": {
            "type": raw_data.get("return_filing_reason", "unknown"),
        },
        "is_defective_return_case": raw_data.get("is_defective_return_case", "unknown"),
        "user_identity": {
            "pan": str(raw_data.get("pan", "")).strip().upper(),
            "aadhaar_number": raw_data.get("aadhaar_number"),
        },
        "entity_type": raw_data.get("entity_type", "individual"),
        "residency_status": {
            "status": raw_data.get("residency_status", "unknown"),
        },
        "income_heads": {
            "salary": _income_head(salary_income),
            "house_property": {
                **_income_head_with_explicit_status(
                    house_property_income,
                    raw_data.get("house_property_has_income"),
                ),
                "property_count": _optional_int(
                    raw_data.get("house_property_count"),
                    ("house_property_count",),
                ),
                "has_self_occupied_property": raw_data.get(
                    "has_self_occupied_property", "unknown"
                ),
                "has_let_out_property": raw_data.get("has_let_out_property", "unknown"),
            },
            "capital_gains": {
                **_income_head(capital_gains_income),
                "has_stcg": raw_data.get("has_stcg", "no"),
                "has_ltcg_112a": raw_data.get(
                    "has_ltcg_112a",
                    "yes" if ltcg_112a_amount > 0 else "no",
                ),
                "ltcg_112a_amount": ltcg_112a_amount,
                "has_other_ltcg": raw_data.get("has_other_ltcg", "no"),
                "has_land_or_building_gains": raw_data.get("has_land_building_gains", "no"),
                "has_land_building_gains": raw_data.get("has_land_building_gains", "no"),
                "has_special_rate_capital_gains": raw_data.get(
                    "has_special_rate_capital_gains", "no"
                ),
            },
            "business_profession": {
                **_income_head(business_income),
                "presumptive_taxation": raw_data.get("presumptive_taxation", "unknown"),
            },
            "other_sources": {
                **_income_head(other_income),
                "has_interest_income": raw_data.get(
                    "has_interest_income",
                    "yes" if other_income > 0 else "no",
                ),
                "has_winnings_or_lottery_income": raw_data.get(
                    "has_winnings_or_lottery_income", "no"
                ),
                "agricultural_income_amount": _number(
                    raw_data.get("agricultural_income_amount", 0),
                    ("agricultural_income_amount",),
                ),
            },
        },
        "deductions": {
            "has_deductions": raw_data.get("has_deductions", "unknown"),
            "section_claims": _normalize_section_claims(raw_data.get("section_claims", [])),
        },
        "foreign_assets": {
            "has_foreign_assets": raw_data.get("has_foreign_assets", "unknown"),
            "has_foreign_income": raw_data.get("has_foreign_income", "unknown"),
        },
        "exemptions_flags": {
            "claims_section_11_exemption": raw_data.get("claims_section_11_exemption", "unknown"),
            "trust_or_institution_case": raw_data.get("trust_or_institution_case", "unknown"),
            "political_party_case": raw_data.get("political_party_case", "unknown"),
            "university_or_research_case": raw_data.get("university_or_research_case", "unknown"),
        },
        "special_conditions": {
            "director_in_company": raw_data.get("director_in_company", "unknown"),
            "unlisted_equity_held": raw_data.get("unlisted_equity_held", "unknown"),
            "brought_forward_losses": raw_data.get("brought_forward_losses", "unknown"),
            "esop_tax_deferred": raw_data.get("esop_tax_deferred", "unknown"),
            "audit_required": raw_data.get("audit_required", "unknown"),
            "presumptive_taxation_ambiguity": raw_data.get(
                "presumptive_taxation_ambiguity", "unknown"
            ),
            "business_profession_ambiguity": raw_data.get(
                "business_profession_ambiguity", "unknown"
            ),
            "capital_gains_edge_case": raw_data.get("capital_gains_edge_case", "unknown"),
            "evidence_mismatch": raw_data.get("evidence_mismatch", "unknown"),
            "low_confidence_extraction": raw_data.get("low_confidence_extraction", "unknown"),
            "pack_resolution_conflict": raw_data.get("pack_resolution_conflict", "unknown"),
        },
    }
    return CanonicalTaxProfile.model_validate(profile)


def _income_head(value: float) -> dict[str, Any]:
    return {"has_income": "yes" if value > 0 else "no", "gross_amount": value}


def _income_head_with_explicit_status(value: float, has_income: Any) -> dict[str, Any]:
    if has_income in ("yes", "no", "unknown"):
        return {"has_income": has_income, "gross_amount": value}
    return _income_head(value)


def _number(value: Any, path: tuple[str | int, ...]) -> float:
    if _is_empty_numeric(value):
        return 0
    if isinstance(value, str):
        value = value.strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        raise _invalid_numeric(path, "number") from None


def _optional_int(value: Any, path: tuple[str | int, ...]) -> int | None:
    if _is_empty_numeric(value):
        return None
    if isinstance(value, str):
        value = value.strip()
    try:
        return int(value)
    except (TypeError, ValueError):
        raise _invalid_numeric(path, "integer") from None


def _normalize_section_claims(section_claims: Any) -> Any:
    if not isinstance(section_claims, list):
        return section_claims

    normalized_claims = []
    for index, claim in enumerate(section_claims):
        if not isinstance(claim, dict):
            normalized_claims.append(claim)
            continue

        normalized_claim = dict(claim)
        if "amount" in normalized_claim:
            normalized_claim["amount"] = _number(
                normalized_claim["amount"],
                ("section_claims", index, "amount"),
            )
        normalized_claims.append(normalized_claim)

    return normalized_claims


def _is_empty_numeric(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _invalid_numeric(path: tuple[str | int, ...], expected_type: str) -> InvalidSchemaError:
    return InvalidSchemaError(
        [
            {
                "type": f"{expected_type}_parsing",
                "loc": ["body", *path],
                "msg": f"Input should be a valid {expected_type}",
            }
        ]
    )

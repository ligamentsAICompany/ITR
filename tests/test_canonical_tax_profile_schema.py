import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.models.tax_profile import CanonicalTaxProfile


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "canonical_tax_profile.schema.json"


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def expected_pydantic_schema():
    schema = CanonicalTaxProfile.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "canonical-tax-profile/v0.1"
    schema["title"] = "Canonical Tax Profile"
    return schema


def valid_payload(**overrides):
    payload = {
        "schema_version": "canonical-tax-profile/v0.1",
        "assessment_year": "2026-27",
        "previous_year": "2025-26",
        "return_filing_reason": {"type": "voluntary"},
        "is_defective_return_case": "no",
        "user_identity": {
            "pan": "ABCDE1234F",
            "aadhaar_number": "123456789012",
            "aadhaar_last4": "9012",
        },
        "entity_type": "individual",
        "residency_status": {
            "status": "resident",
            "days_in_india_current_py": 220,
        },
        "income_heads": {
            "salary": {
                "has_income": "yes",
                "gross_amount": 1200000,
                "employer_count": 1,
                "has_pension_income": "no",
            },
            "house_property": {
                "has_income": "yes",
                "gross_amount": 0,
                "property_count": 1,
                "has_self_occupied_property": "yes",
                "has_let_out_property": "no",
            },
            "capital_gains": {
                "has_income": "yes",
                "gross_amount": 100000,
                "has_short_term_gains": "no",
                "has_long_term_gains": "yes",
                "has_equity_or_mutual_fund_gains": "yes",
                "has_stcg": "no",
                "has_ltcg_112a": "yes",
                "ltcg_112a_amount": 100000,
                "has_other_ltcg": "no",
                "has_land_or_building_gains": "no",
                "has_land_building_gains": "no",
                "has_special_rate_capital_gains": "no",
            },
            "business_profession": {
                "has_income": "yes",
                "gross_amount": 1800000,
                "nature": "profession",
                "presumptive_taxation": "yes",
                "section_44ad_applicable": "no",
                "section_44ada_applicable": "yes",
                "section_44ae_applicable": "no",
            },
            "other_sources": {
                "has_income": "yes",
                "gross_amount": 45000,
                "has_interest_income": "yes",
                "has_dividend_income": "yes",
                "has_winnings_or_lottery_income": "no",
                "agricultural_income_amount": 3000,
            },
        },
        "deductions": {
            "has_deductions": "yes",
            "section_claims": [{"section_code": "80C", "amount": 150000}],
        },
        "foreign_assets": {
            "has_foreign_assets": "no",
            "has_foreign_income": "no",
            "has_signing_authority_outside_india": "no",
        },
        "exemptions_flags": {
            "claims_section_11_exemption": "no",
            "trust_or_institution_case": "no",
            "political_party_case": "no",
            "university_or_research_case": "no",
        },
        "special_conditions": {
            "director_in_company": "no",
            "unlisted_equity_held": "no",
            "brought_forward_losses": "no",
            "esop_tax_deferred": "no",
            "audit_required": "no",
            "presumptive_taxation_ambiguity": "no",
            "business_profession_ambiguity": "no",
            "capital_gains_edge_case": "no",
            "evidence_mismatch": "no",
            "low_confidence_extraction": "no",
            "pack_resolution_conflict": "no",
        },
    }
    deep_merge(payload, overrides)
    return payload


def deep_merge(target, overrides):
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = value


def assert_schema_rejects(schema, payload):
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=str)
    assert errors


def test_canonical_schema_is_generated_from_strict_pydantic_model():
    assert load_schema() == expected_pydantic_schema()


def test_valid_canonical_payload_passes_schema_and_backend_validation():
    payload = valid_payload()

    Draft202012Validator(load_schema()).validate(payload)
    assert CanonicalTaxProfile.model_validate(payload).model_dump(mode="json") == payload


def test_invalid_nested_extra_field_fails_schema_and_backend_validation():
    payload = valid_payload()
    payload["income_heads"]["salary"]["unexpected_field"] = "accepted by loose schemas"

    assert_schema_rejects(load_schema(), payload)
    with pytest.raises(ValidationError):
        CanonicalTaxProfile.model_validate(payload)


def test_schema_covers_all_nested_sections_from_backend_model():
    schema = load_schema()
    required_sections = {
        "return_filing_reason",
        "user_identity",
        "residency_status",
        "income_heads",
        "deductions",
        "foreign_assets",
        "exemptions_flags",
        "special_conditions",
    }
    assert required_sections <= schema["properties"].keys()

    payload = valid_payload()
    for section in required_sections:
        sectionless_payload = copy.deepcopy(payload)
        sectionless_payload.pop(section)

        if CanonicalTaxProfile.model_fields[section].is_required():
            assert_schema_rejects(schema, sectionless_payload)

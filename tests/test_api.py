import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def sample_profile(**overrides):
    profile = {
        "schema_version": "canonical-tax-profile/v0.1",
        "assessment_year": "2026-27",
        "previous_year": "2025-26",
        "return_filing_reason": {"type": "voluntary"},
        "is_defective_return_case": "no",
        "user_identity": {"pan": "ABCDE1234F", "aadhaar_number": "123456789012"},
        "entity_type": "individual",
        "residency_status": {"status": "resident"},
        "income_heads": {
            "salary": {"has_income": "yes", "gross_amount": 1200000},
            "house_property": {"has_income": "no", "gross_amount": 0},
            "capital_gains": {"has_income": "no", "gross_amount": 0},
            "business_profession": {
                "has_income": "no",
                "gross_amount": 0,
                "presumptive_taxation": "no",
            },
            "other_sources": {"has_income": "no", "gross_amount": 0},
        },
        "deductions": {"has_deductions": "unknown", "section_claims": []},
        "foreign_assets": {"has_foreign_assets": "no", "has_foreign_income": "no"},
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
    deep_merge(profile, overrides)
    return profile


def deep_merge(target, overrides):
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = value


def test_normalize_returns_canonical_profile_defaults_for_partial_input():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "abcde1234f",
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "entity_type": "individual",
            "residency_status": "resident",
            "salary_income": 1200000,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    print("/normalize", payload)
    assert payload["user_identity"]["pan"] == "ABCDE1234F"
    assert payload["income_heads"]["salary"]["has_income"] == "yes"
    assert payload["return_filing_reason"]["type"] == "unknown"
    assert response.headers["x-request-id"]
    assert response.headers["x-trace-id"]


def test_normalize_preserves_house_property_details_from_ui_payload():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "abcde1234f",
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "entity_type": "individual",
            "residency_status": "resident",
            "salary_income": 1200000,
            "house_property_has_income": "yes",
            "house_property_income": 0,
            "house_property_count": 1,
            "has_self_occupied_property": "yes",
            "has_let_out_property": "no",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    house_property = payload["income_heads"]["house_property"]
    assert house_property["has_income"] == "yes"
    assert house_property["gross_amount"] == 0
    assert house_property["property_count"] == 1
    assert house_property["has_self_occupied_property"] == "yes"
    assert house_property["has_let_out_property"] == "no"


def test_normalize_preserves_deduction_amounts_from_ui_payload():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "abcde1234f",
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "entity_type": "individual",
            "residency_status": "resident",
            "salary_income": 1200000,
            "has_deductions": "yes",
            "section_claims": [
                {"section_code": "80C", "amount": 150000},
                {"section_code": "80D", "amount": 25000},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["deductions"]["has_deductions"] == "yes"
    assert payload["deductions"]["section_claims"] == [
        {"section_code": "80C", "amount": 150000},
        {"section_code": "80D", "amount": 25000},
    ]


def test_normalize_keeps_capital_gains_subtype_mapping():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "abcde1234f",
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "entity_type": "individual",
            "residency_status": "resident",
            "salary_income": 1200000,
            "capital_gains_income": 100000,
            "has_stcg": "no",
            "has_ltcg_112a": "yes",
            "ltcg_112a_amount": 100000,
            "has_other_ltcg": "no",
            "has_land_building_gains": "no",
            "has_special_rate_capital_gains": "no",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    capital_gains = payload["income_heads"]["capital_gains"]
    assert capital_gains["has_income"] == "yes"
    assert capital_gains["has_ltcg_112a"] == "yes"
    assert capital_gains["ltcg_112a_amount"] == 100000
    assert capital_gains["has_stcg"] == "no"
    assert capital_gains["has_other_ltcg"] == "no"
    assert capital_gains["has_land_building_gains"] == "no"
    assert capital_gains["has_special_rate_capital_gains"] == "no"


@pytest.mark.parametrize("salary_income", [" ", "   "])
def test_normalize_treats_whitespace_salary_income_as_empty(salary_income):
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "ABCDE1234F",
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "entity_type": "individual",
            "residency_status": "resident",
            "salary_income": salary_income,
        },
    )

    assert response.status_code == 200
    salary = response.json()["income_heads"]["salary"]
    assert salary["has_income"] == "no"
    assert salary["gross_amount"] == 0


def test_normalize_rejects_non_numeric_salary_income_as_invalid_schema():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "ABCDE1234F",
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "entity_type": "individual",
            "residency_status": "resident",
            "salary_income": "abc",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"] == "invalid_schema"
    assert "abc" not in response.text


def test_normalize_treats_whitespace_deduction_amount_as_empty():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "ABCDE1234F",
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "entity_type": "individual",
            "residency_status": "resident",
            "has_deductions": "yes",
            "section_claims": [{"section_code": "80C", "amount": " "}],
        },
    )

    assert response.status_code == 200
    assert response.json()["deductions"]["section_claims"] == [
        {"section_code": "80C", "amount": 0}
    ]


def test_normalize_treats_whitespace_house_property_count_as_empty():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "ABCDE1234F",
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "entity_type": "individual",
            "residency_status": "resident",
            "house_property_count": " ",
        },
    )

    assert response.status_code == 200
    assert response.json()["income_heads"]["house_property"]["property_count"] is None


def test_normalize_accepts_trimmed_numeric_strings():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "ABCDE1234F",
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "entity_type": "individual",
            "residency_status": "resident",
            "salary_income": " 1200000 ",
            "ltcg_112a_amount": " 100000 ",
            "house_property_count": " 2 ",
            "has_deductions": "yes",
            "section_claims": [{"section_code": "80C", "amount": " 150000 "}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["income_heads"]["salary"]["gross_amount"] == 1200000
    assert payload["income_heads"]["capital_gains"]["ltcg_112a_amount"] == 100000
    assert payload["income_heads"]["house_property"]["property_count"] == 2
    assert payload["deductions"]["section_claims"] == [
        {"section_code": "80C", "amount": 150000}
    ]


def test_normalize_empty_and_omitted_numeric_values_remain_empty():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "ABCDE1234F",
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "entity_type": "individual",
            "residency_status": "resident",
            "salary_income": "",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["income_heads"]["salary"]["gross_amount"] == 0
    assert payload["income_heads"]["house_property"]["property_count"] is None


def test_itr_decision_wraps_existing_deterministic_classifier():
    response = client.post(
        "/v1/itr-decision",
        json=sample_profile(),
        headers={"X-Request-ID": "req-test-1", "X-Trace-ID": "trace-test-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    print("/itr-decision", payload)
    assert payload["candidate_itr"] == "ITR-1"
    assert "ITR1_ELIGIBLE_SIMPLE_RESIDENT_INDIVIDUAL" in payload["reason_codes"]
    assert payload["confidence"] == "high"
    assert response.headers["x-request-id"] == "req-test-1"
    assert response.headers["x-trace-id"] == "trace-test-1"


def test_missing_fields_returns_classifier_missing_fields():
    profile = sample_profile()
    del profile["previous_year"]
    profile["return_filing_reason"]["type"] = "unknown"

    response = client.post("/v1/missing-fields", json=profile)

    assert response.status_code == 200
    payload = response.json()
    print("/missing-fields", payload)
    assert "previous_year" in payload["missing_fields"]
    assert "return_filing_reason.type" in payload["missing_fields"]


def test_explain_uses_slm_wrapper_without_overriding_itr():
    decision = {
        "candidate_itr": "ITR-2",
        "reason_codes": [
            "ITR1_DISQUALIFIED_CAPITAL_GAINS",
            "ITR2_ELIGIBLE_NON_BUSINESS_INCOME",
        ],
        "missing_fields": [],
        "confidence": "high",
    }

    response = client.post("/v1/explain", json=decision)

    assert response.status_code == 200
    payload = response.json()
    print("/explain", payload)
    assert payload["candidate_itr"] == "ITR-2"
    assert "deterministic engine selected ITR-2" in payload["explanation"]
    assert "capital gains" in payload["explanation"].lower()
    assert "ITR-4" not in payload["explanation"]


def test_clarify_returns_minimum_question_for_missing_fields():
    response = client.post(
        "/v1/clarify",
        json={
            "missing_fields": ["income_heads.business_profession.presumptive_taxation"],
            "context": {"candidate_itr": "ITR-3"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    print("/clarify", payload)
    assert payload["question"]
    assert "presumptive" in payload["question"].lower()
    assert "ITR-3" not in payload["question"]


def test_invalid_schema_returns_400():
    response = client.post("/v1/itr-decision", json={"entity_type": "individual"})

    assert response.status_code == 400
    payload = response.json()
    print("invalid schema", payload)
    assert payload["error"] == "invalid_schema"

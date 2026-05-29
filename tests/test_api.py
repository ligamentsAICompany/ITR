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

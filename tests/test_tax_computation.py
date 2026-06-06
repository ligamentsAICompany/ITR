from copy import deepcopy
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.decision import ITRDecisionResponse
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport, ValidationStatus
from app.services.tax_computation_service import (
    MissingTaxConfigError,
    TaxComputationService,
)
from itr_engine import legal_packs


client = TestClient(app)


def sample_profile(**overrides):
    profile = {
        "schema_version": "canonical-tax-profile/v0.2",
        "assessment_year": "2026-27",
        "previous_year": "2025-26",
        "return_filing_reason": {"type": "voluntary"},
        "is_defective_return_case": "no",
        "user_identity": {"pan": "ABCDE1234F", "aadhaar_number": "123456789012"},
        "entity_type": "individual",
        "residency_status": {"status": "resident"},
        "income_heads": {
            "salary": {"has_income": "yes", "gross_amount": 1200000, "employer_name": "Example Pvt Ltd"},
            "house_property": {"has_income": "no", "gross_amount": 0},
            "capital_gains": {"has_income": "no", "gross_amount": 0},
            "business_profession": {
                "has_income": "no",
                "gross_amount": 0,
                "presumptive_taxation": "no",
            },
            "other_sources": {"has_income": "no", "gross_amount": 0},
        },
        "deductions": {"has_deductions": "no", "section_claims": []},
        "tax_payments": {
            "tds_salary": 0,
            "tds_other": 0,
            "tcs": 0,
            "advance_tax": 0,
            "self_assessment_tax": 0,
        },
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


def profile_model(**overrides):
    return CanonicalTaxProfile.model_validate(sample_profile(**overrides))


def decision(candidate_itr="ITR-1"):
    return ITRDecisionResponse(
        candidate_itr=candidate_itr,
        reason_codes=["TEST_REASON"],
        missing_fields=[],
        confidence="high",
    )


def compute(**overrides):
    return TaxComputationService().compute(
        profile=profile_model(**overrides),
        candidate_itr=decision(),
    )


def test_salary_only_new_regime_uses_rebate_and_returns_zero_liability():
    result = compute()

    assert result.selected_regime == "new"
    assert result.income.gross_total_income == 1200000
    assert result.income.standard_deduction == 75000
    assert result.taxable_income == 1125000
    assert result.tax_before_rebate == 52500
    assert result.rebate == 52500
    assert result.total_tax_liability == 0
    assert result.refund_due == 0
    assert result.tax_payable == 0
    assert [step.step_key for step in result.steps]


def test_salary_with_80c_80d_old_regime_applies_configured_deduction_limits():
    result = TaxComputationService().compute(
        profile=profile_model(
            deductions={
                "has_deductions": "yes",
                "section_claims": [
                    {"section_code": "80C", "amount": 200000},
                    {"section_code": "80D", "amount": 30000},
                ],
            }
        ),
        candidate_itr=decision(),
        selected_regime="old",
    )

    assert result.selected_regime == "old"
    assert result.deductions.claimed_total == 230000
    assert result.deductions.allowed_total == 175000
    assert result.taxable_income == 975000
    assert result.total_tax_liability == 111800


def test_tds_credit_can_create_refund():
    result = compute(tax_payments={"tds_salary": 50000})

    assert result.credits.total_credits == 50000
    assert result.refund_due == 50000
    assert result.tax_payable == 0


def test_tax_payable_when_liability_exceeds_credits():
    result = compute(income_heads={"salary": {"gross_amount": 2500000}})

    assert result.tax_before_rebate == 307500
    assert result.cess == 12300
    assert result.total_tax_liability == 319800
    assert result.tax_payable == 319800


def test_presumptive_professional_income_is_included_without_guessing_margin():
    result = compute(
        income_heads={
            "salary": {"has_income": "no", "gross_amount": 0},
            "business_profession": {
                "has_income": "yes",
                "gross_amount": 900000,
                "presumptive_taxation": "yes",
                "nature": "profession",
            },
        }
    )

    assert result.income.business_profession_income == 900000
    assert result.taxable_income == 900000
    assert not any("margin" in warning.message.lower() for warning in result.warnings)


def test_interest_income_is_included_in_gross_total_income():
    result = compute(
        income_heads={
            "other_sources": {
                "has_income": "yes",
                "gross_amount": 100000,
                "has_interest_income": "yes",
                "interest_savings_amount": 40000,
                "interest_fixed_deposit_amount": 60000,
            }
        }
    )

    assert result.income.other_sources_income == 100000
    assert result.income.gross_total_income == 1300000
    assert result.taxable_income == 1225000


def test_house_property_missing_detail_adds_warning_not_guess():
    result = compute(
        income_heads={
            "house_property": {
                "has_income": "yes",
                "gross_amount": 0,
                "property_count": 1,
                "has_self_occupied_property": "yes",
            }
        }
    )

    assert result.income.house_property_income == 0
    assert any(warning.code == "HOUSE_PROPERTY_DETAIL_LIMITED" for warning in result.warnings)


def test_special_rate_capital_gains_are_included_and_warned_when_detail_not_supported():
    result = compute(
        income_heads={
            "capital_gains": {
                "has_income": "yes",
                "gross_amount": 150000,
                "has_special_rate_capital_gains": "yes",
            }
        }
    )

    assert result.income.capital_gains_income == 150000
    assert result.income.capital_gains_subtypes["special_rate"] == 150000
    assert any(warning.code == "SPECIAL_RATE_CAPITAL_GAINS_NOT_COMPUTED" for warning in result.warnings)


def test_special_rate_subtype_does_not_create_extra_capital_gains():
    result = compute(
        income_heads={
            "capital_gains": {
                "has_income": "yes",
                "gross_amount": 150000,
                "has_ltcg_112a": "yes",
                "ltcg_112a_amount": 150000,
                "has_special_rate_capital_gains": "yes",
            }
        }
    )

    assert result.income.capital_gains_income == 150000
    assert result.income.capital_gains_subtypes["ltcg_112a"] == 150000
    assert "special_rate" not in result.income.capital_gains_subtypes


def test_agricultural_income_is_explicitly_warned_not_silently_taxed():
    result = compute(
        income_heads={
            "other_sources": {
                "has_income": "yes",
                "gross_amount": 10000,
                "agricultural_income_amount": 6000,
            }
        }
    )

    assert result.income.other_sources_income == 10000
    assert any(warning.code == "AGRICULTURAL_INCOME_NOT_TAX_COMPUTED" for warning in result.warnings)


def test_validation_failed_result_is_preview_with_warning():
    report = ValidationReport(
        validation_run_id="validation-failed",
        overall_status=ValidationStatus.FAILED,
        readiness_score=40,
        evidence_summary={"document_count": 0, "approved_extracted_field_count": 0, "document_types": []},
    )

    result = TaxComputationService().compute(
        profile=profile_model(),
        candidate_itr=decision(),
        validation_report=report,
    )

    assert result.is_preview is True
    assert any(warning.code == "VALIDATION_FAILED_PREVIEW_ONLY" for warning in result.warnings)


def test_selected_regime_uses_requested_config():
    new_result = compute()
    old_result = TaxComputationService().compute(
        profile=profile_model(),
        candidate_itr=decision(),
        selected_regime="old",
    )

    assert new_result.selected_regime == "new"
    assert old_result.selected_regime == "old"
    assert new_result.total_tax_liability != old_result.total_tax_liability


def test_legal_pack_value_changes_output_without_service_code_changes(monkeypatch):
    baseline = compute()
    current_pack = legal_packs.LEGAL_PACKS["AY2026-27"]
    changed_new_regime = replace(current_pack.tax_computation.new_regime, standard_deduction=100000)
    changed_tax_pack = replace(current_pack.tax_computation, new_regime=changed_new_regime)
    monkeypatch.setitem(legal_packs.LEGAL_PACKS, "AY2026-27", replace(current_pack, tax_computation=changed_tax_pack))

    changed = compute()

    assert changed.taxable_income == baseline.taxable_income - 25000
    assert changed.tax_before_rebate != baseline.tax_before_rebate


def test_missing_legal_pack_config_fails_safely(monkeypatch):
    current_pack = legal_packs.LEGAL_PACKS["AY2026-27"]
    broken_tax_pack = replace(current_pack.tax_computation, new_regime=None)
    monkeypatch.setitem(legal_packs.LEGAL_PACKS, "AY2026-27", replace(current_pack, tax_computation=broken_tax_pack))

    with pytest.raises(MissingTaxConfigError, match="new regime"):
        compute()


def test_compute_does_not_mutate_profile():
    profile_dict = sample_profile()
    original = deepcopy(profile_dict)
    profile = CanonicalTaxProfile.model_validate(profile_dict)

    TaxComputationService().compute(profile=profile, candidate_itr=decision())

    assert profile.model_dump(mode="json") == CanonicalTaxProfile.model_validate(original).model_dump(mode="json")


def test_explanation_is_grounded_and_masks_sensitive_identifiers():
    result = compute()
    explanation = TaxComputationService().explain(result)

    assert str(result.total_tax_liability) in explanation.explanation
    assert "ABCDE1234F" not in explanation.explanation
    assert "123456789012" not in explanation.explanation
    assert explanation.grounded_computation_id == result.computation_id


def test_tax_compute_api_shape_and_in_memory_retrieval():
    response = client.post(
        "/v1/tax/compute",
        json={"profile": sample_profile(), "candidate_itr": decision().model_dump(), "selected_regime": "new"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["selected_regime"] == "new"
    assert payload["total_tax_liability"] == 0
    assert "pan" not in str(payload).lower()
    assert "ABCDE1234F" not in str(payload)
    assert "123456789012" not in str(payload)

    get_response = client.get(f"/v1/tax/{payload['computation_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["computation_id"] == payload["computation_id"]


def test_tax_explain_api_uses_stored_computation_only():
    compute_response = client.post(
        "/v1/tax/compute",
        json={"profile": sample_profile(), "candidate_itr": decision().model_dump()},
    )
    computation_id = compute_response.json()["computation_id"]

    explain_response = client.post("/v1/tax/explain", json={"computation_id": computation_id})

    assert explain_response.status_code == 200
    payload = explain_response.json()
    assert payload["grounded_computation_id"] == computation_id
    assert "total tax liability" in payload["explanation"].lower()
    assert "ABCDE1234F" not in payload["explanation"]

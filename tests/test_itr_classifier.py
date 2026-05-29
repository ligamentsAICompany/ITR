import json
from dataclasses import replace

from itr_engine import legal_packs
from itr_engine.classifier import classify_itr


def base_profile(**overrides):
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
            "salary": {"has_income": "no", "gross_amount": 0},
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


def assert_result(profile, expected_itr, expected_reason):
    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == expected_itr
    assert expected_reason in result["reason_codes"]
    return result


def print_case(profile, result):
    print("\nINPUT")
    print(json.dumps(profile, indent=2, sort_keys=True))
    print("OUTPUT")
    print(json.dumps(result, indent=2, sort_keys=True))
    print("REASONING")
    print(", ".join(result["reason_codes"]))


def test_salary_only_resident_individual_classifies_as_itr_1():
    profile = base_profile(
        income_heads={"salary": {"has_income": "yes", "gross_amount": 1200000}}
    )

    assert_result(profile, "ITR-1", "ITR1_ELIGIBLE_SIMPLE_RESIDENT_INDIVIDUAL")


def test_salary_with_capital_gains_classifies_as_itr_2():
    profile = base_profile(
        income_heads={
            "salary": {"has_income": "yes", "gross_amount": 1200000},
            "capital_gains": {"has_income": "yes", "gross_amount": 150000},
        }
    )

    assert_result(profile, "ITR-2", "ITR2_ELIGIBLE_NON_BUSINESS_INCOME")


def itr1_allowed_112a_profile(**overrides):
    profile = base_profile(
        income_heads={
            "salary": {"has_income": "yes", "gross_amount": 1280000},
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
                "has_ltcg_112a": "yes",
                "ltcg_112a_amount": 100000,
                "has_stcg": "no",
                "has_other_ltcg": "no",
                "has_land_building_gains": "no",
                "has_special_rate_capital_gains": "no",
            },
            "other_sources": {
                "has_income": "yes",
                "gross_amount": 28000,
                "has_interest_income": "yes",
                "has_dividend_income": "no",
                "has_winnings_or_lottery_income": "no",
                "agricultural_income_amount": 4500,
            },
        },
        deductions={
            "has_deductions": "yes",
            "section_claims": [
                {"section_code": "80C", "amount": 150000},
                {"section_code": "80D", "amount": 25000},
            ],
        },
    )
    deep_merge(profile, overrides)
    return profile


def test_itr1_allows_only_112a_ltcg_within_threshold():
    profile = itr1_allowed_112a_profile()

    result = assert_result(profile, "ITR-1", "ITR1_ELIGIBLE_SIMPLE_RESIDENT_INDIVIDUAL")
    assert "ITR1_ALLOWED_112A_LTCG_WITHIN_THRESHOLD" in result["reason_codes"]
    assert "ITR1_ALLOWED_AGRICULTURAL_INCOME_WITHIN_THRESHOLD" in result["reason_codes"]
    assert "ITR1_DISQUALIFIED_CAPITAL_GAINS" not in result["reason_codes"]


def test_itr1_disqualifies_112a_ltcg_above_threshold():
    profile = itr1_allowed_112a_profile(
        income_heads={
            "capital_gains": {
                "gross_amount": 130000,
                "ltcg_112a_amount": 130000,
            }
        }
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-2"
    assert "ITR1_DISQUALIFIED_112A_LTCG_ABOVE_THRESHOLD" in result["reason_codes"]


def test_itr1_disqualifies_short_term_capital_gains():
    profile = itr1_allowed_112a_profile(
        income_heads={
            "capital_gains": {
                "gross_amount": 50000,
                "has_ltcg_112a": "no",
                "ltcg_112a_amount": 0,
                "has_stcg": "yes",
            }
        }
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-2"
    assert "ITR1_DISQUALIFIED_SHORT_TERM_CAPITAL_GAINS" in result["reason_codes"]


def test_itr1_disqualifies_other_ltcg():
    profile = itr1_allowed_112a_profile(
        income_heads={
            "capital_gains": {
                "gross_amount": 50000,
                "has_ltcg_112a": "no",
                "ltcg_112a_amount": 0,
                "has_other_ltcg": "yes",
            }
        }
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-2"
    assert "ITR1_DISQUALIFIED_OTHER_LTCG" in result["reason_codes"]


def test_itr1_disqualifies_land_building_gains():
    profile = itr1_allowed_112a_profile(
        income_heads={
            "capital_gains": {
                "gross_amount": 500000,
                "has_ltcg_112a": "no",
                "ltcg_112a_amount": 0,
                "has_land_building_gains": "yes",
            }
        }
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-2"
    assert "ITR1_DISQUALIFIED_LAND_BUILDING_GAINS" in result["reason_codes"]


def test_itr1_disqualifies_special_rate_capital_gains():
    profile = itr1_allowed_112a_profile(
        income_heads={
            "capital_gains": {
                "gross_amount": 50000,
                "has_ltcg_112a": "no",
                "ltcg_112a_amount": 0,
                "has_special_rate_capital_gains": "yes",
            }
        }
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-2"
    assert "ITR1_DISQUALIFIED_SPECIAL_RATE_CAPITAL_GAINS" in result["reason_codes"]


def test_non_presumptive_business_income_classifies_as_itr_3():
    profile = base_profile(
        income_heads={
            "business_profession": {
                "has_income": "yes",
                "gross_amount": 1800000,
                "presumptive_taxation": "no",
            }
        }
    )

    assert_result(profile, "ITR-3", "ITR3_ELIGIBLE_BUSINESS_PROFESSION")


def test_presumptive_business_income_classifies_as_itr_4():
    profile = base_profile(
        income_heads={
            "business_profession": {
                "has_income": "yes",
                "gross_amount": 1800000,
                "presumptive_taxation": "yes",
            }
        }
    )

    assert_result(profile, "ITR-4", "ITR4_ELIGIBLE_PRESUMPTIVE_INCOME")


def presumptive_professional_profile(**overrides):
    profile = base_profile(
        income_heads={
            "business_profession": {
                "has_income": "yes",
                "gross_amount": 2400000,
                "presumptive_taxation": "yes",
                "nature": "profession",
            },
            "other_sources": {
                "has_income": "yes",
                "gross_amount": 42000,
                "has_interest_income": "yes",
                "agricultural_income_amount": 0,
            },
        }
    )
    deep_merge(profile, overrides)
    return profile


def test_presumptive_professional_with_112a_ltcg_within_threshold_classifies_as_itr_4():
    profile = presumptive_professional_profile(
        income_heads={
            "capital_gains": {
                "has_income": "yes",
                "gross_amount": 80000,
                "has_ltcg_112a": "yes",
                "ltcg_112a_amount": 80000,
                "has_stcg": "no",
                "has_other_ltcg": "no",
                "has_land_building_gains": "no",
                "has_special_rate_capital_gains": "no",
            }
        }
    )

    result = assert_result(profile, "ITR-4", "ITR4_ELIGIBLE_PRESUMPTIVE_INCOME")
    assert "ITR4_ALLOWED_112A_LTCG_WITHIN_THRESHOLD" in result["reason_codes"]


def test_presumptive_professional_with_112a_ltcg_above_threshold_not_itr_4():
    profile = presumptive_professional_profile(
        income_heads={
            "capital_gains": {
                "has_income": "yes",
                "gross_amount": 130000,
                "has_ltcg_112a": "yes",
                "ltcg_112a_amount": 130000,
                "has_stcg": "no",
                "has_other_ltcg": "no",
                "has_land_building_gains": "no",
                "has_special_rate_capital_gains": "no",
            }
        }
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-3"
    assert "ITR4_DISQUALIFIED_112A_LTCG_ABOVE_THRESHOLD" in result["reason_codes"]


def test_presumptive_professional_with_short_term_capital_gains_not_itr_4():
    profile = presumptive_professional_profile(
        income_heads={
            "capital_gains": {
                "has_income": "yes",
                "gross_amount": 50000,
                "has_ltcg_112a": "no",
                "ltcg_112a_amount": 0,
                "has_stcg": "yes",
                "has_other_ltcg": "no",
                "has_land_building_gains": "no",
                "has_special_rate_capital_gains": "no",
            }
        }
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-3"
    assert "ITR4_DISQUALIFIED_SHORT_TERM_CAPITAL_GAINS" in result["reason_codes"]


def test_presumptive_professional_with_property_sale_gains_not_itr_4():
    profile = presumptive_professional_profile(
        income_heads={
            "capital_gains": {
                "has_income": "yes",
                "gross_amount": 500000,
                "has_ltcg_112a": "no",
                "ltcg_112a_amount": 0,
                "has_stcg": "no",
                "has_other_ltcg": "no",
                "has_land_building_gains": "yes",
                "has_special_rate_capital_gains": "no",
            }
        }
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-3"
    assert "ITR4_DISQUALIFIED_LAND_BUILDING_CAPITAL_GAINS" in result["reason_codes"]


def test_presumptive_professional_with_agricultural_income_within_threshold_can_be_itr_4():
    profile = presumptive_professional_profile(
        income_heads={
            "other_sources": {
                "has_income": "yes",
                "gross_amount": 45000,
                "has_interest_income": "yes",
                "agricultural_income_amount": 3000,
            }
        }
    )

    result = assert_result(profile, "ITR-4", "ITR4_ELIGIBLE_PRESUMPTIVE_INCOME")
    assert "ITR4_ALLOWED_AGRICULTURAL_INCOME_WITHIN_THRESHOLD" in result["reason_codes"]


def test_presumptive_professional_with_agricultural_income_above_threshold_not_itr_4():
    profile = presumptive_professional_profile(
        income_heads={
            "other_sources": {
                "has_income": "yes",
                "gross_amount": 9000,
                "has_interest_income": "yes",
                "agricultural_income_amount": 6000,
            }
        }
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-3"
    assert "ITR4_DISQUALIFIED_AGRICULTURAL_INCOME_ABOVE_THRESHOLD" in result["reason_codes"]


def test_neha_presumptive_professional_112a_ltcg_classifies_as_itr_4():
    profile = presumptive_professional_profile(
        income_heads={
            "capital_gains": {
                "has_income": "yes",
                "gross_amount": 80000,
                "has_ltcg_112a": "yes",
                "ltcg_112a_amount": 80000,
                "has_stcg": "no",
                "has_other_ltcg": "no",
                "has_land_building_gains": "no",
                "has_special_rate_capital_gains": "no",
            },
            "other_sources": {
                "has_income": "yes",
                "gross_amount": 45000,
                "has_interest_income": "yes",
                "agricultural_income_amount": 3000,
            },
        }
    )

    result = assert_result(profile, "ITR-4", "ITR4_ELIGIBLE_PRESUMPTIVE_INCOME")
    assert result["confidence"] == "high"


def test_itr4_112a_ltcg_limit_is_legal_pack_driven(monkeypatch):
    profile = presumptive_professional_profile(
        income_heads={
            "capital_gains": {
                "has_income": "yes",
                "gross_amount": 80000,
                "has_ltcg_112a": "yes",
                "ltcg_112a_amount": 80000,
                "has_stcg": "no",
                "has_other_ltcg": "no",
                "has_land_building_gains": "no",
                "has_special_rate_capital_gains": "no",
            }
        }
    )
    baseline = classify_itr(profile)
    assert baseline["candidate_itr"] == "ITR-4"

    current_pack = legal_packs.LEGAL_PACKS["AY2026-27"]
    stricter_pack = replace(
        current_pack,
        itr4=replace(current_pack.itr4, ltcg_112a_limit=50000),
    )
    monkeypatch.setitem(legal_packs.LEGAL_PACKS, "AY2026-27", stricter_pack)

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-3"
    assert "ITR4_DISQUALIFIED_112A_LTCG_ABOVE_THRESHOLD" in result["reason_codes"]


def test_foreign_assets_exclude_itr_1_and_classify_as_itr_2_for_non_business_case():
    profile = base_profile(
        income_heads={"salary": {"has_income": "yes", "gross_amount": 1200000}},
        foreign_assets={"has_foreign_assets": "yes", "has_foreign_income": "no"},
    )

    result = assert_result(profile, "ITR-2", "ITR2_ELIGIBLE_NON_BUSINESS_INCOME")
    assert "ITR1_EXCLUDED_FOREIGN_ASSETS_OR_INCOME" in result["reason_codes"]
    assert result["confidence"] == "medium"


def test_ambiguous_business_income_returns_missing_fields_and_low_confidence():
    profile = base_profile(
        income_heads={
            "business_profession": {
                "has_income": "yes",
                "gross_amount": 900000,
                "presumptive_taxation": "unknown",
            }
        },
        special_conditions={"presumptive_taxation_ambiguity": "yes"},
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-3"
    assert "income_heads.business_profession.presumptive_taxation" in result["missing_fields"]
    assert "BUSINESS_PRESUMPTIVE_STATUS_UNKNOWN" in result["reason_codes"]
    assert result["confidence"] == "low"


def test_entity_based_company_classifies_as_itr_6():
    profile = base_profile(entity_type="company")

    assert_result(profile, "ITR-6", "ITR6_ENTITY_COMPANY")


def test_entity_based_trust_case_classifies_as_itr_7():
    profile = base_profile(
        entity_type="trust",
        exemptions_flags={"trust_or_institution_case": "yes"},
    )

    assert_result(profile, "ITR-7", "ITR7_EXEMPT_OR_INSTITUTIONAL_ENTITY")


def test_entity_based_llp_classifies_as_itr_5():
    profile = base_profile(entity_type="llp")

    assert_result(profile, "ITR-5", "ITR5_ENTITY_NON_COMPANY_NON_ITR7")


def test_missing_later_phase_filing_context_fields_are_reported():
    profile = base_profile()
    profile.pop("previous_year")
    profile["return_filing_reason"]["type"] = "unknown"
    profile["is_defective_return_case"] = "unknown"

    result = classify_itr(profile)
    print_case(profile, result)
    assert "previous_year" in result["missing_fields"]
    assert "return_filing_reason.type" in result["missing_fields"]
    assert "is_defective_return_case" in result["missing_fields"]
    assert result["confidence"] == "low"


def test_priority_selects_itr_7_over_itr_6_when_company_has_exempt_signal():
    profile = base_profile(
        entity_type="company",
        exemptions_flags={"claims_section_11_exemption": "yes"},
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-7"
    assert "ITR7_ELIGIBLE_EXEMPT_OR_INSTITUTIONAL_ENTITY" in result["reason_codes"]
    assert "ITR6_DISQUALIFIED_ITR7_SIGNAL_PRESENT" in result["reason_codes"]


def test_foreign_business_presumptive_disqualifies_itr_4_and_falls_to_itr_3():
    profile = base_profile(
        income_heads={
            "business_profession": {
                "has_income": "yes",
                "gross_amount": 1800000,
                "presumptive_taxation": "yes",
            }
        },
        foreign_assets={"has_foreign_assets": "yes", "has_foreign_income": "no"},
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-3"
    assert "ITR4_DISQUALIFIED_FOREIGN_ASSETS_OR_INCOME" in result["reason_codes"]
    assert "ITR3_ELIGIBLE_BUSINESS_PROFESSION" in result["reason_codes"]
    assert "ITR2_DISQUALIFIED_BUSINESS_PROFESSION_INCOME" in result["reason_codes"]


def test_non_resident_presumptive_business_does_not_classify_as_itr_4():
    profile = base_profile(
        residency_status={"status": "non_resident"},
        income_heads={
            "business_profession": {
                "has_income": "yes",
                "gross_amount": 1800000,
                "presumptive_taxation": "yes",
            }
        },
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-3"
    assert "ITR4_DISQUALIFIED_NOT_RESIDENT" in result["reason_codes"]
    assert "ITR3_ELIGIBLE_BUSINESS_PROFESSION" in result["reason_codes"]


def test_salary_with_director_flag_does_not_classify_as_itr_1():
    profile = base_profile(
        income_heads={"salary": {"has_income": "yes", "gross_amount": 1200000}},
        special_conditions={"director_in_company": "yes"},
    )

    result = classify_itr(profile)
    print_case(profile, result)
    assert result["candidate_itr"] == "ITR-2"
    assert "ITR1_DISQUALIFIED_DIRECTOR_IN_COMPANY" in result["reason_codes"]
    assert "ITR2_ELIGIBLE_NON_BUSINESS_INCOME" in result["reason_codes"]

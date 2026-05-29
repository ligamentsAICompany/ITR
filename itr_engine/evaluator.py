"""Evaluation layer for deterministic ITR classification."""

from itr_engine import rules
from itr_engine.formatter import format_result

PRIORITY_ORDER = ["ITR-7", "ITR-6", "ITR-5", "ITR-4", "ITR-3", "ITR-2", "ITR-1"]


def evaluate_profile(profile):
    missing_fields = rules.required_missing_fields(profile)
    disqualifications = compute_disqualifications(profile)
    eligibility = compute_eligibility(profile, disqualifications)

    candidate_itr = select_candidate_by_priority(eligibility)
    reason_codes = collect_reason_codes(profile, disqualifications, eligibility, candidate_itr)
    confidence = score_confidence(profile, missing_fields)

    if missing_fields:
        reason_codes.append("MISSING_FIELDS_PRESENT")
    if rules.has_review_signal(profile):
        reason_codes.append("HUMAN_REVIEW_SIGNAL_PRESENT")

    return format_result(candidate_itr, reason_codes, missing_fields, confidence)


def compute_disqualifications(profile):
    """Compute hard disqualifications before any candidate is selected."""
    entity_type = profile.get("entity_type")
    disqualified = {itr: [] for itr in PRIORITY_ORDER}

    if rules.has_itr7_signal(profile) and entity_type == "company":
        disqualified["ITR-6"].append("ITR6_DISQUALIFIED_ITR7_SIGNAL_PRESENT")

    if entity_type in rules.ITR5_ENTITIES and rules.has_itr7_signal(profile):
        disqualified["ITR-5"].append("ITR5_DISQUALIFIED_ITR7_SIGNAL_PRESENT")

    if entity_type == "individual":
        add_itr1_disqualifications(profile, disqualified["ITR-1"])

    if rules.is_individual_bucket(profile):
        if rules.has_business_income(profile):
            disqualified["ITR-2"].append("ITR2_DISQUALIFIED_BUSINESS_PROFESSION_INCOME")

    if entity_type in rules.ITR4_ALLOWED_ENTITIES:
        add_itr4_disqualifications(profile, disqualified["ITR-4"])

    return disqualified


def add_itr1_disqualifications(profile, reasons):
    if not rules.is_resident(profile):
        reasons.extend(
            [
                "ITR1_DISQUALIFIED_NOT_RESIDENT_INDIVIDUAL",
                "ITR1_EXCLUDED_NOT_RESIDENT_INDIVIDUAL",
            ]
        )
    if not rules.income_within_simple_threshold(profile):
        reasons.extend(
            [
                "ITR1_DISQUALIFIED_TOTAL_INCOME_ABOVE_50_LAKH",
                "ITR1_EXCLUDED_TOTAL_INCOME_ABOVE_50_LAKH",
            ]
        )
    if rules.has_business_income(profile):
        reasons.extend(
            [
                "ITR1_DISQUALIFIED_BUSINESS_PROFESSION_INCOME",
                "ITR1_EXCLUDED_BUSINESS_PROFESSION_INCOME",
            ]
        )
    add_itr1_capital_gains_disqualifications(profile, reasons)
    if not rules.agricultural_income_within_itr4_limit(profile):
        reasons.extend(
            [
                "ITR1_DISQUALIFIED_AGRICULTURAL_INCOME_ABOVE_THRESHOLD",
                "ITR1_EXCLUDED_AGRICULTURAL_INCOME_ABOVE_THRESHOLD",
            ]
        )
    if rules.has_foreign_assets_or_income(profile):
        reasons.extend(
            [
                "ITR1_DISQUALIFIED_FOREIGN_ASSETS_OR_INCOME",
                "ITR1_EXCLUDED_FOREIGN_ASSETS_OR_INCOME",
            ]
        )
    if rules.get_path(profile, "special_conditions.director_in_company") == "yes":
        reasons.extend(
            ["ITR1_DISQUALIFIED_DIRECTOR_IN_COMPANY", "ITR1_EXCLUDED_SPECIAL_CONDITION"]
        )
    if rules.get_path(profile, "special_conditions.unlisted_equity_held") == "yes":
        reasons.extend(
            ["ITR1_DISQUALIFIED_UNLISTED_EQUITY_HELD", "ITR1_EXCLUDED_SPECIAL_CONDITION"]
        )
    if any(
        rules.get_path(profile, f"special_conditions.{field}") == "yes"
        for field in (
            "brought_forward_losses",
            "esop_tax_deferred",
            "capital_gains_edge_case",
            "pack_resolution_conflict",
        )
    ):
        reasons.extend(["ITR1_DISQUALIFIED_SPECIAL_CONDITION", "ITR1_EXCLUDED_SPECIAL_CONDITION"])


def add_itr1_capital_gains_disqualifications(profile, reasons):
    if not rules.has_capital_gains(profile):
        return
    has_disqualifying_capital_gains_subtype = False
    if rules.has_stcg(profile):
        has_disqualifying_capital_gains_subtype = True
        reasons.extend(
            [
                "ITR1_DISQUALIFIED_SHORT_TERM_CAPITAL_GAINS",
                "ITR1_EXCLUDED_SHORT_TERM_CAPITAL_GAINS",
            ]
        )
    if (
        rules.has_ltcg_112a(profile)
        and rules.ltcg_112a_amount(profile)
        > rules.legal_pack_for_profile(profile).itr4.ltcg_112a_limit
    ):
        has_disqualifying_capital_gains_subtype = True
        reasons.extend(
            [
                "ITR1_DISQUALIFIED_112A_LTCG_ABOVE_THRESHOLD",
                "ITR1_EXCLUDED_112A_LTCG_ABOVE_THRESHOLD",
            ]
        )
    if rules.has_other_ltcg(profile):
        has_disqualifying_capital_gains_subtype = True
        reasons.extend(["ITR1_DISQUALIFIED_OTHER_LTCG", "ITR1_EXCLUDED_OTHER_LTCG"])
    if rules.has_land_building_gains(profile):
        has_disqualifying_capital_gains_subtype = True
        reasons.extend(
            [
                "ITR1_DISQUALIFIED_LAND_BUILDING_GAINS",
                "ITR1_EXCLUDED_LAND_BUILDING_GAINS",
            ]
        )
    if rules.has_special_rate_capital_gains(profile):
        has_disqualifying_capital_gains_subtype = True
        reasons.extend(
            [
                "ITR1_DISQUALIFIED_SPECIAL_RATE_CAPITAL_GAINS",
                "ITR1_EXCLUDED_SPECIAL_RATE_CAPITAL_GAINS",
            ]
        )
    if not rules.has_only_allowed_112a_ltcg(profile) and not has_disqualifying_capital_gains_subtype:
        reasons.extend(["ITR1_DISQUALIFIED_CAPITAL_GAINS", "ITR1_EXCLUDED_CAPITAL_GAINS"])


def add_itr4_disqualifications(profile, reasons):
    if not rules.is_resident(profile):
        reasons.extend(["ITR4_DISQUALIFIED_NOT_RESIDENT", "ITR4_EXCLUDED_NOT_RESIDENT"])
    if not rules.has_business_income(profile):
        reasons.append("ITR4_DISQUALIFIED_NO_BUSINESS_PROFESSION_INCOME")
    if rules.is_presumptive_business(profile) != "yes":
        reasons.extend(["ITR4_DISQUALIFIED_NOT_PRESUMPTIVE", "ITR4_EXCLUDED_NOT_PRESUMPTIVE"])
        if rules.is_presumptive_business(profile) == "unknown":
            reasons.append("BUSINESS_PRESUMPTIVE_STATUS_UNKNOWN")
    if not rules.income_within_simple_threshold(profile):
        reasons.extend(
            [
                "ITR4_DISQUALIFIED_TOTAL_INCOME_ABOVE_50_LAKH",
                "ITR4_EXCLUDED_TOTAL_INCOME_ABOVE_50_LAKH",
            ]
        )
    add_itr4_capital_gains_disqualifications(profile, reasons)
    if not rules.agricultural_income_within_itr4_limit(profile):
        reasons.extend(
            [
                "ITR4_DISQUALIFIED_AGRICULTURAL_INCOME_ABOVE_THRESHOLD",
                "ITR4_EXCLUDED_AGRICULTURAL_INCOME_ABOVE_THRESHOLD",
            ]
        )
    if rules.has_foreign_assets_or_income(profile):
        reasons.extend(
            [
                "ITR4_DISQUALIFIED_FOREIGN_ASSETS_OR_INCOME",
                "ITR4_EXCLUDED_FOREIGN_ASSETS_OR_INCOME",
            ]
        )
    if rules.has_special_exclusion(profile):
        reasons.extend(["ITR4_DISQUALIFIED_SPECIAL_CONDITION", "ITR4_EXCLUDED_SPECIAL_CONDITION"])


def add_itr4_capital_gains_disqualifications(profile, reasons):
    if not rules.has_capital_gains(profile):
        return
    if rules.has_stcg(profile):
        reasons.extend(
            [
                "ITR4_DISQUALIFIED_SHORT_TERM_CAPITAL_GAINS",
                "ITR4_EXCLUDED_SHORT_TERM_CAPITAL_GAINS",
            ]
        )
    if (
        rules.has_ltcg_112a(profile)
        and rules.ltcg_112a_amount(profile)
        > rules.legal_pack_for_profile(profile).itr4.ltcg_112a_limit
    ):
        reasons.extend(
            [
                "ITR4_DISQUALIFIED_112A_LTCG_ABOVE_THRESHOLD",
                "ITR4_EXCLUDED_112A_LTCG_ABOVE_THRESHOLD",
            ]
        )
    if rules.has_other_ltcg(profile):
        reasons.extend(["ITR4_DISQUALIFIED_OTHER_LTCG", "ITR4_EXCLUDED_OTHER_LTCG"])
    if rules.has_land_building_gains(profile):
        reasons.extend(
            [
                "ITR4_DISQUALIFIED_LAND_BUILDING_CAPITAL_GAINS",
                "ITR4_EXCLUDED_LAND_BUILDING_CAPITAL_GAINS",
            ]
        )
    if rules.has_special_rate_capital_gains(profile):
        reasons.extend(
            [
                "ITR4_DISQUALIFIED_SPECIAL_RATE_CAPITAL_GAINS",
                "ITR4_EXCLUDED_SPECIAL_RATE_CAPITAL_GAINS",
            ]
        )
    if not rules.has_only_allowed_112a_ltcg(profile) and not any(
        reason.startswith("ITR4_DISQUALIFIED_") and "CAPITAL_GAINS" in reason
        for reason in reasons
    ):
        reasons.extend(["ITR4_DISQUALIFIED_CAPITAL_GAINS", "ITR4_EXCLUDED_CAPITAL_GAINS"])


def compute_eligibility(profile, disqualifications):
    entity_type = profile.get("entity_type")
    itr1_eligible = entity_type == "individual" and not disqualifications["ITR-1"]

    eligibility = {
        "ITR-7": rules.has_itr7_signal(profile) or entity_type == "trust",
        "ITR-6": entity_type == "company" and not disqualifications["ITR-6"],
        "ITR-5": entity_type in rules.ITR5_ENTITIES and not disqualifications["ITR-5"],
        "ITR-4": (
            entity_type in rules.ITR4_ALLOWED_ENTITIES
            and rules.has_business_income(profile)
            and rules.is_presumptive_business(profile) == "yes"
            and not disqualifications["ITR-4"]
        ),
        "ITR-3": rules.is_individual_bucket(profile) and rules.has_business_income(profile),
        "ITR-2": (
            rules.is_individual_bucket(profile)
            and not rules.has_business_income(profile)
            and not disqualifications["ITR-2"]
            and not itr1_eligible
        ),
        "ITR-1": itr1_eligible,
    }
    return eligibility


def select_candidate_by_priority(eligibility):
    for candidate in PRIORITY_ORDER:
        if eligibility[candidate]:
            return candidate
    return ""


def collect_reason_codes(profile, disqualifications, eligibility, candidate_itr):
    reason_codes = []
    for candidate in PRIORITY_ORDER:
        reason_codes.extend(disqualifications[candidate])

    if candidate_itr:
        reason_codes.extend(eligibility_reason_codes(candidate_itr))
    else:
        reason_codes.append("ENTITY_TYPE_UNSUPPORTED_OR_UNKNOWN")

    if eligibility.get("ITR-4") and eligibility.get("ITR-3") and candidate_itr == "ITR-4":
        reason_codes.append("PRIORITY_SELECTED_ITR4_OVER_ITR3")
    if candidate_itr == "ITR-4" and eligibility.get("ITR-4"):
        reason_codes.extend(allowed_itr4_companion_reason_codes(profile))
    if candidate_itr == "ITR-1" and eligibility.get("ITR-1"):
        reason_codes.extend(allowed_itr1_companion_reason_codes(profile))

    return reason_codes


def allowed_itr1_companion_reason_codes(profile):
    reason_codes = []
    if (
        rules.has_ltcg_112a(profile)
        and rules.ltcg_112a_amount(profile)
        <= rules.legal_pack_for_profile(profile).itr4.ltcg_112a_limit
    ):
        reason_codes.append("ITR1_ALLOWED_112A_LTCG_WITHIN_THRESHOLD")
    if (
        0
        < rules.agricultural_income_amount(profile)
        <= rules.legal_pack_for_profile(profile).itr4.agricultural_income_limit
    ):
        reason_codes.append("ITR1_ALLOWED_AGRICULTURAL_INCOME_WITHIN_THRESHOLD")
    return reason_codes


def allowed_itr4_companion_reason_codes(profile):
    reason_codes = []
    if (
        rules.has_ltcg_112a(profile)
        and rules.ltcg_112a_amount(profile)
        <= rules.legal_pack_for_profile(profile).itr4.ltcg_112a_limit
    ):
        reason_codes.append("ITR4_ALLOWED_112A_LTCG_WITHIN_THRESHOLD")
    if (
        0
        < rules.agricultural_income_amount(profile)
        <= rules.legal_pack_for_profile(profile).itr4.agricultural_income_limit
    ):
        reason_codes.append("ITR4_ALLOWED_AGRICULTURAL_INCOME_WITHIN_THRESHOLD")
    return reason_codes


def eligibility_reason_codes(candidate_itr):
    return {
        "ITR-7": [
            "ITR7_ELIGIBLE_EXEMPT_OR_INSTITUTIONAL_ENTITY",
            "ITR7_EXEMPT_OR_INSTITUTIONAL_ENTITY",
        ],
        "ITR-6": ["ITR6_ENTITY_COMPANY"],
        "ITR-5": ["ITR5_ENTITY_NON_COMPANY_NON_ITR7"],
        "ITR-4": ["ITR4_ELIGIBLE_PRESUMPTIVE_INCOME"],
        "ITR-3": ["ITR3_ELIGIBLE_BUSINESS_PROFESSION"],
        "ITR-2": ["ITR2_ELIGIBLE_NON_BUSINESS_INCOME"],
        "ITR-1": ["ITR1_ELIGIBLE_SIMPLE_RESIDENT_INDIVIDUAL"],
    }[candidate_itr]


def score_confidence(profile, missing_fields):
    if missing_fields:
        return "low"
    if rules.unknown_income_heads(profile):
        return "low"
    if rules.has_review_signal(profile):
        return "medium"
    return "high"

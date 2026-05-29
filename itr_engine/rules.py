"""Pure deterministic rule helpers for ITR classification.

These helpers do not call AI services, external APIs, databases, or network
resources. They only inspect the canonical tax profile supplied by the caller.
"""

from itr_engine.legal_packs import legal_pack_for_profile

INDIVIDUAL_BUCKET_ENTITIES = {"individual", "huf"}
ITR4_ALLOWED_ENTITIES = {"individual", "huf", "firm"}
ITR5_ENTITIES = {
    "firm",
    "llp",
    "aop",
    "boi",
    "local_authority",
    "cooperative_society",
    "ajp",
    "estate",
    "business_trust",
    "investment_fund",
    "representative_assessee",
    "society",
    "other",
}
ITR7_SIGNAL_FIELDS = {
    "claims_section_11_exemption",
    "trust_or_institution_case",
    "political_party_case",
    "university_or_research_case",
}
RETURN_FILING_REASON_TYPES = {"voluntary", "mandatory", "notice", "unknown"}
YES_NO_UNKNOWN = {"yes", "no", "unknown"}


def get_path(profile, path, default=None):
    current = profile
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def has_income(profile, head):
    return get_path(profile, f"income_heads.{head}.has_income") == "yes"


def income_unknown(profile, head):
    return get_path(profile, f"income_heads.{head}.has_income") == "unknown"


def amount(profile, head):
    value = get_path(profile, f"income_heads.{head}.gross_amount", 0)
    return value if isinstance(value, (int, float)) else 0


def total_gross_income(profile):
    return sum(
        amount(profile, head)
        for head in (
            "salary",
            "house_property",
            "capital_gains",
            "business_profession",
            "other_sources",
        )
    )


def has_business_income(profile):
    return has_income(profile, "business_profession")


def has_capital_gains(profile):
    return has_income(profile, "capital_gains")


def has_stcg(profile):
    return get_path(profile, "income_heads.capital_gains.has_stcg") == "yes"


def has_ltcg_112a(profile):
    return get_path(profile, "income_heads.capital_gains.has_ltcg_112a") == "yes"


def ltcg_112a_amount(profile):
    value = get_path(profile, "income_heads.capital_gains.ltcg_112a_amount", 0)
    return value if isinstance(value, (int, float)) else 0


def has_other_ltcg(profile):
    return get_path(profile, "income_heads.capital_gains.has_other_ltcg") == "yes"


def has_land_building_gains(profile):
    return get_path(profile, "income_heads.capital_gains.has_land_building_gains") == "yes"


def has_special_rate_capital_gains(profile):
    return get_path(profile, "income_heads.capital_gains.has_special_rate_capital_gains") == "yes"


def has_only_allowed_112a_ltcg(profile):
    if not has_capital_gains(profile):
        return True
    return (
        has_ltcg_112a(profile)
        and ltcg_112a_amount(profile) <= legal_pack_for_profile(profile).itr4.ltcg_112a_limit
        and not has_stcg(profile)
        and not has_other_ltcg(profile)
        and not has_land_building_gains(profile)
        and not has_special_rate_capital_gains(profile)
    )


def agricultural_income_amount(profile):
    value = get_path(profile, "income_heads.other_sources.agricultural_income_amount", 0)
    return value if isinstance(value, (int, float)) else 0


def agricultural_income_within_itr4_limit(profile):
    return (
        agricultural_income_amount(profile)
        <= legal_pack_for_profile(profile).itr4.agricultural_income_limit
    )


def has_foreign_assets_or_income(profile):
    return (
        get_path(profile, "foreign_assets.has_foreign_assets") == "yes"
        or get_path(profile, "foreign_assets.has_foreign_income") == "yes"
    )


def has_itr7_signal(profile):
    return any(
        get_path(profile, f"exemptions_flags.{field}") == "yes"
        for field in ITR7_SIGNAL_FIELDS
    )


def has_special_exclusion(profile):
    return any(
        get_path(profile, f"special_conditions.{field}") == "yes"
        for field in (
            "director_in_company",
            "unlisted_equity_held",
            "brought_forward_losses",
            "esop_tax_deferred",
            "capital_gains_edge_case",
            "pack_resolution_conflict",
        )
    )


def has_review_signal(profile):
    if has_foreign_assets_or_income(profile) or has_itr7_signal(profile):
        return True
    return any(
        get_path(profile, f"special_conditions.{field}") == "yes"
        for field in (
            "business_profession_ambiguity",
            "presumptive_taxation_ambiguity",
            "capital_gains_edge_case",
            "evidence_mismatch",
            "low_confidence_extraction",
            "pack_resolution_conflict",
        )
    )


def is_presumptive_business(profile):
    return get_path(profile, "income_heads.business_profession.presumptive_taxation")


def is_resident(profile):
    return get_path(profile, "residency_status.status") == "resident"


def is_individual_bucket(profile):
    return profile.get("entity_type") in INDIVIDUAL_BUCKET_ENTITIES


def income_within_simple_threshold(profile):
    return total_gross_income(profile) <= legal_pack_for_profile(profile).itr4.total_income_limit


def required_missing_fields(profile):
    missing = []
    required_paths = [
        "assessment_year",
        "previous_year",
        "return_filing_reason.type",
        "is_defective_return_case",
        "user_identity.pan",
        "entity_type",
        "residency_status.status",
        "income_heads.salary.has_income",
        "income_heads.house_property.has_income",
        "income_heads.capital_gains.has_income",
        "income_heads.business_profession.has_income",
        "income_heads.other_sources.has_income",
        "foreign_assets.has_foreign_assets",
        "foreign_assets.has_foreign_income",
    ]
    for path in required_paths:
        value = get_path(profile, path)
        if value in (None, "", "unknown"):
            missing.append(path)

    if has_business_income(profile) and is_presumptive_business(profile) == "unknown":
        missing.append("income_heads.business_profession.presumptive_taxation")

    if has_capital_gains(profile) and get_path(
        profile, "special_conditions.brought_forward_losses"
    ) == "unknown":
        missing.append("special_conditions.brought_forward_losses")

    if (
        has_capital_gains(profile)
        and has_foreign_assets_or_income(profile)
        and get_path(profile, "special_conditions.capital_gains_edge_case") == "unknown"
    ):
        missing.append("special_conditions.capital_gains_edge_case")

    return missing


def unknown_income_heads(profile):
    return [
        f"income_heads.{head}.has_income"
        for head in (
            "salary",
            "house_property",
            "capital_gains",
            "business_profession",
            "other_sources",
        )
        if income_unknown(profile, head)
    ]

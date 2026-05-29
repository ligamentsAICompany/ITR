"""Pydantic models for canonical ITR classification input."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

YesNoUnknown = Literal["yes", "no", "unknown"]
EntityType = Literal[
    "individual",
    "huf",
    "firm",
    "llp",
    "company",
    "trust",
    "society",
    "aop",
    "boi",
    "local_authority",
    "cooperative_society",
    "ajp",
    "estate",
    "business_trust",
    "investment_fund",
    "representative_assessee",
    "other",
]
ResidencyStatusType = Literal["resident", "rnor", "non_resident", "unknown"]
ReturnFilingReasonType = Literal["voluntary", "mandatory", "notice", "unknown"]


class StrictModel(BaseModel):
    """Base model that rejects unknown fields for deterministic contracts."""

    model_config = ConfigDict(extra="forbid")


class UserIdentity(StrictModel):
    pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    aadhaar_number: str | None = Field(default=None, pattern=r"^[0-9]{12}$")
    aadhaar_last4: str | None = Field(default=None, pattern=r"^[0-9]{4}$")


class ReturnFilingReason(StrictModel):
    type: ReturnFilingReasonType = "unknown"


class ResidencyStatus(StrictModel):
    status: ResidencyStatusType
    days_in_india_current_py: int | None = Field(default=None, ge=0, le=366)


class IncomeHead(StrictModel):
    has_income: YesNoUnknown
    gross_amount: float | None = Field(default=None, ge=0)


class SalaryIncome(IncomeHead):
    employer_count: int | None = Field(default=None, ge=0)
    has_pension_income: YesNoUnknown | None = None


class HousePropertyIncome(IncomeHead):
    property_count: int | None = Field(default=None, ge=0)
    has_self_occupied_property: YesNoUnknown | None = None
    has_let_out_property: YesNoUnknown | None = None


class CapitalGainsIncome(IncomeHead):
    has_short_term_gains: YesNoUnknown | None = None
    has_long_term_gains: YesNoUnknown | None = None
    has_equity_or_mutual_fund_gains: YesNoUnknown | None = None
    has_stcg: YesNoUnknown | None = None
    has_ltcg_112a: YesNoUnknown | None = None
    ltcg_112a_amount: float | None = Field(default=None, ge=0)
    has_other_ltcg: YesNoUnknown | None = None
    has_land_or_building_gains: YesNoUnknown | None = None
    has_land_building_gains: YesNoUnknown | None = None
    has_special_rate_capital_gains: YesNoUnknown | None = None


class BusinessProfessionIncome(IncomeHead):
    nature: Literal["business", "profession", "both", "unknown"] | None = None
    presumptive_taxation: YesNoUnknown = "unknown"
    section_44ad_applicable: YesNoUnknown | None = None
    section_44ada_applicable: YesNoUnknown | None = None
    section_44ae_applicable: YesNoUnknown | None = None


class OtherSourcesIncome(IncomeHead):
    has_interest_income: YesNoUnknown | None = None
    has_dividend_income: YesNoUnknown | None = None
    has_winnings_or_lottery_income: YesNoUnknown | None = None
    agricultural_income_amount: float | None = Field(default=None, ge=0)


class IncomeHeads(StrictModel):
    salary: SalaryIncome
    house_property: HousePropertyIncome
    capital_gains: CapitalGainsIncome
    business_profession: BusinessProfessionIncome
    other_sources: OtherSourcesIncome


class DeductionClaim(StrictModel):
    section_code: str
    amount: float = Field(ge=0)


class Deductions(StrictModel):
    has_deductions: YesNoUnknown
    section_claims: list[DeductionClaim] = Field(default_factory=list)


class ForeignAssets(StrictModel):
    has_foreign_assets: YesNoUnknown
    has_foreign_income: YesNoUnknown
    has_signing_authority_outside_india: YesNoUnknown | None = None


class ExemptionsFlags(StrictModel):
    claims_section_11_exemption: YesNoUnknown
    trust_or_institution_case: YesNoUnknown
    political_party_case: YesNoUnknown
    university_or_research_case: YesNoUnknown


class SpecialConditions(StrictModel):
    director_in_company: YesNoUnknown
    unlisted_equity_held: YesNoUnknown
    brought_forward_losses: YesNoUnknown
    esop_tax_deferred: YesNoUnknown
    audit_required: YesNoUnknown
    presumptive_taxation_ambiguity: YesNoUnknown
    business_profession_ambiguity: YesNoUnknown
    capital_gains_edge_case: YesNoUnknown
    evidence_mismatch: YesNoUnknown
    low_confidence_extraction: YesNoUnknown
    pack_resolution_conflict: YesNoUnknown


class CanonicalTaxProfile(StrictModel):
    schema_version: Literal["canonical-tax-profile/v0.1"]
    assessment_year: str = Field(pattern=r"^20\d{2}-\d{2}$")
    previous_year: str | None = Field(default=None, pattern=r"^20\d{2}-\d{2}$")
    return_filing_reason: ReturnFilingReason = Field(default_factory=ReturnFilingReason)
    is_defective_return_case: YesNoUnknown = "unknown"
    user_identity: UserIdentity
    entity_type: EntityType
    residency_status: ResidencyStatus
    income_heads: IncomeHeads
    deductions: Deductions
    foreign_assets: ForeignAssets
    exemptions_flags: ExemptionsFlags
    special_conditions: SpecialConditions

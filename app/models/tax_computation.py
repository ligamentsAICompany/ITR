"""Strict public models for deterministic tax computation."""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.decision import ITRDecisionResponse
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport, mask_sensitive

TaxRegime = Literal["old", "new"]


class StrictTaxComputationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=False)


class DecimalModel(StrictTaxComputationModel):
    @field_serializer("*", when_used="json")
    def serialize_decimal_fields(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral_value() else float(value)
        return value


class IncomeBreakdown(DecimalModel):
    salary_income: Decimal = Field(ge=0)
    standard_deduction: Decimal = Field(ge=0)
    house_property_income: Decimal
    business_profession_income: Decimal = Field(ge=0)
    capital_gains_income: Decimal = Field(ge=0)
    capital_gains_subtypes: dict[str, Decimal] = Field(default_factory=dict)
    other_sources_income: Decimal = Field(ge=0)
    gross_total_income: Decimal


class AppliedDeduction(DecimalModel):
    section_code: str
    claimed_amount: Decimal = Field(ge=0)
    allowed_amount: Decimal = Field(ge=0)
    limit: Decimal = Field(ge=0)
    notes: str


class DeductionBreakdown(DecimalModel):
    claimed_total: Decimal = Field(ge=0)
    allowed_total: Decimal = Field(ge=0)
    disallowed_total: Decimal = Field(ge=0)
    applied: list[AppliedDeduction] = Field(default_factory=list)


class TaxCreditBreakdown(DecimalModel):
    tds_salary: Decimal = Field(ge=0)
    tds_other: Decimal = Field(ge=0)
    tcs: Decimal = Field(ge=0)
    advance_tax: Decimal = Field(ge=0)
    self_assessment_tax: Decimal = Field(ge=0)
    total_credits: Decimal = Field(ge=0)


class TaxComputationStep(DecimalModel):
    step_key: str
    label: str
    amount: Decimal
    formula: str


class TaxComputationWarning(StrictTaxComputationModel):
    code: str
    message: str

    @field_validator("message")
    @classmethod
    def mask_sensitive_warning(cls, value: str) -> str:
        return str(mask_sensitive(value))


class TaxComputationResult(DecimalModel):
    computation_id: str
    assessment_year: str
    previous_year: str | None = None
    selected_regime: TaxRegime
    regime_label: str
    default_regime: TaxRegime
    candidate_itr: str
    is_preview: bool = False
    income: IncomeBreakdown
    deductions: DeductionBreakdown
    taxable_income: Decimal = Field(ge=0)
    tax_before_rebate: Decimal = Field(ge=0)
    rebate: Decimal = Field(ge=0)
    surcharge: Decimal = Field(ge=0)
    cess: Decimal = Field(ge=0)
    total_tax_liability: Decimal = Field(ge=0)
    credits: TaxCreditBreakdown
    refund_due: Decimal = Field(ge=0)
    tax_payable: Decimal = Field(ge=0)
    warnings: list[TaxComputationWarning] = Field(default_factory=list)
    steps: list[TaxComputationStep] = Field(default_factory=list)


class TaxComputeRequest(StrictTaxComputationModel):
    profile: CanonicalTaxProfile
    candidate_itr: ITRDecisionResponse
    validation_report: ValidationReport | None = None
    selected_regime: TaxRegime | None = None


class TaxExplainRequest(StrictTaxComputationModel):
    computation_id: str


class TaxExplanationResponse(StrictTaxComputationModel):
    grounded_computation_id: str
    explanation: str
    warnings: list[TaxComputationWarning] = Field(default_factory=list)

    @field_validator("explanation")
    @classmethod
    def mask_sensitive_explanation(cls, value: str) -> str:
        return str(mask_sensitive(value))

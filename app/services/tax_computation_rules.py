"""Pure deterministic rules for tax computation.

All assessment-year constants are supplied by the legal-pack layer. This module
only applies those constants to canonical profile values.
"""

from decimal import Decimal, ROUND_HALF_UP

from app.models.tax_computation import (
    AppliedDeduction,
    DeductionBreakdown,
    IncomeBreakdown,
    TaxComputationStep,
    TaxComputationWarning,
    TaxCreditBreakdown,
)
from app.models.tax_profile import CanonicalTaxProfile, DeductionClaim
from itr_engine.legal_packs import TaxRegimeConfig, TaxSlab

ZERO = Decimal("0")
RUPEE = Decimal("1")


def money(value: object) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(RUPEE, rounding=ROUND_HALF_UP)


def round_money(value: Decimal) -> Decimal:
    return value.quantize(RUPEE, rounding=ROUND_HALF_UP)


def compute_income_breakdown(
    profile: CanonicalTaxProfile,
    regime: TaxRegimeConfig,
) -> tuple[IncomeBreakdown, list[TaxComputationWarning]]:
    warnings: list[TaxComputationWarning] = []
    income_heads = profile.income_heads

    salary_gross = money(income_heads.salary.gross_amount)
    standard_deduction = min(salary_gross, money(regime.standard_deduction))

    house_property = income_heads.house_property
    house_property_income = money(house_property.gross_amount)
    housing_interest = money(house_property.interest_on_housing_loan)
    if housing_interest:
        house_property_income = round_money(house_property_income - housing_interest)
    if house_property.has_income == "yes" and (
        house_property.annual_value is None or house_property.interest_on_housing_loan is None
    ):
        warnings.append(
            TaxComputationWarning(
                code="HOUSE_PROPERTY_DETAIL_LIMITED",
                message="House property computation used provided net amounts only; missing annual value or loan interest detail was not guessed.",
            )
        )

    business_income = money(income_heads.business_profession.gross_amount)
    if income_heads.business_profession.has_income == "yes" and income_heads.business_profession.presumptive_taxation == "unknown":
        warnings.append(
            TaxComputationWarning(
                code="BUSINESS_DETAIL_LIMITED",
                message="Business/profession income was included from captured amount; presumptive status is unknown and was not inferred.",
            )
        )

    capital_gains = income_heads.capital_gains
    capital_gains_income = money(capital_gains.gross_amount)
    capital_gains_subtypes = {
        "stcg": money(capital_gains.stcg_amount),
        "ltcg_112a": money(capital_gains.ltcg_112a_amount),
        "other_ltcg": money(capital_gains.other_ltcg_amount),
    }
    known_capital_subtypes = sum(capital_gains_subtypes.values(), ZERO)
    if capital_gains.has_special_rate_capital_gains == "yes":
        special_rate_amount = capital_gains_income - known_capital_subtypes
        capital_gains_subtypes["special_rate"] = max(special_rate_amount, capital_gains_income if special_rate_amount <= ZERO else ZERO)
        warnings.append(
            TaxComputationWarning(
                code="SPECIAL_RATE_CAPITAL_GAINS_NOT_COMPUTED",
                message="Capital gains were included in total income, but detailed special-rate computation is not supported in this phase.",
            )
        )
    capital_gains_subtypes = {key: value for key, value in capital_gains_subtypes.items() if value}

    other_sources_income = money(income_heads.other_sources.gross_amount)
    interest_parts = (
        money(income_heads.other_sources.interest_savings_amount)
        + money(income_heads.other_sources.interest_fixed_deposit_amount)
        + money(income_heads.other_sources.interest_other_amount)
    )
    if interest_parts > other_sources_income:
        other_sources_income = interest_parts

    gross_total_income = round_money(
        salary_gross + house_property_income + business_income + capital_gains_income + other_sources_income
    )
    return (
        IncomeBreakdown(
            salary_income=salary_gross,
            standard_deduction=standard_deduction,
            house_property_income=house_property_income,
            business_profession_income=business_income,
            capital_gains_income=capital_gains_income,
            capital_gains_subtypes=capital_gains_subtypes,
            other_sources_income=other_sources_income,
            gross_total_income=gross_total_income,
        ),
        warnings,
    )


def compute_deductions(
    claims: list[DeductionClaim],
    regime: TaxRegimeConfig,
) -> tuple[DeductionBreakdown, list[TaxComputationWarning]]:
    warnings: list[TaxComputationWarning] = []
    configured_limits = {limit.section_code.upper(): limit for limit in regime.deduction_limits}
    applied: list[AppliedDeduction] = []
    claimed_total = ZERO
    allowed_total = ZERO

    for claim in claims:
        section_code = claim.section_code.upper()
        claimed_amount = money(claim.amount)
        claimed_total += claimed_amount
        limit_config = configured_limits.get(section_code)
        if limit_config is None:
            if claimed_amount:
                warnings.append(
                    TaxComputationWarning(
                        code="DEDUCTION_NOT_ALLOWED_OR_NOT_CONFIGURED",
                        message=f"Deduction {section_code} was claimed but is not configured for the selected regime.",
                    )
                )
            continue
        limit = money(limit_config.limit)
        allowed_amount = min(claimed_amount, limit)
        allowed_total += allowed_amount
        applied.append(
            AppliedDeduction(
                section_code=section_code,
                claimed_amount=claimed_amount,
                allowed_amount=allowed_amount,
                limit=limit,
                notes=limit_config.notes,
            )
        )

    claimed_total = round_money(claimed_total)
    allowed_total = round_money(allowed_total)
    return (
        DeductionBreakdown(
            claimed_total=claimed_total,
            allowed_total=allowed_total,
            disallowed_total=round_money(max(claimed_total - allowed_total, ZERO)),
            applied=applied,
        ),
        warnings,
    )


def compute_taxable_income(income: IncomeBreakdown, deductions: DeductionBreakdown) -> Decimal:
    return round_money(max(income.gross_total_income - income.standard_deduction - deductions.allowed_total, ZERO))


def compute_slab_tax(taxable_income: Decimal, slabs: tuple[TaxSlab, ...]) -> Decimal:
    tax = ZERO
    for slab in slabs:
        lower = money(slab.lower)
        upper = money(slab.upper) if slab.upper is not None else taxable_income
        if taxable_income <= lower:
            continue
        taxable_in_slab = min(taxable_income, upper) - lower
        if taxable_in_slab > ZERO:
            tax += taxable_in_slab * Decimal(str(slab.rate))
    return round_money(tax)


def compute_rebate(taxable_income: Decimal, tax_before_rebate: Decimal, regime: TaxRegimeConfig) -> Decimal:
    if taxable_income <= money(regime.rebate_threshold):
        return round_money(min(tax_before_rebate, money(regime.rebate_limit)))
    return ZERO


def compute_surcharge(_tax_after_rebate: Decimal, regime: TaxRegimeConfig) -> Decimal:
    if regime.surcharge_rules:
        return ZERO
    return ZERO


def compute_cess(tax_after_rebate_and_surcharge: Decimal, regime: TaxRegimeConfig) -> Decimal:
    return round_money(tax_after_rebate_and_surcharge * Decimal(str(regime.cess_rate)))


def compute_tax_credits(profile: CanonicalTaxProfile) -> TaxCreditBreakdown:
    payments = profile.tax_payments
    tds_salary = money(payments.tds_salary)
    tds_other = money(payments.tds_other)
    tcs = money(payments.tcs)
    advance_tax = money(payments.advance_tax)
    self_assessment_tax = money(payments.self_assessment_tax)
    total = round_money(tds_salary + tds_other + tcs + advance_tax + self_assessment_tax)
    return TaxCreditBreakdown(
        tds_salary=tds_salary,
        tds_other=tds_other,
        tcs=tcs,
        advance_tax=advance_tax,
        self_assessment_tax=self_assessment_tax,
        total_credits=total,
    )


def compute_refund_or_payable(total_tax_liability: Decimal, credits: TaxCreditBreakdown) -> tuple[Decimal, Decimal]:
    if credits.total_credits > total_tax_liability:
        return round_money(credits.total_credits - total_tax_liability), ZERO
    return ZERO, round_money(total_tax_liability - credits.total_credits)


def build_computation_steps(
    income: IncomeBreakdown,
    deductions: DeductionBreakdown,
    taxable_income: Decimal,
    tax_before_rebate: Decimal,
    rebate: Decimal,
    surcharge: Decimal,
    cess: Decimal,
    total_tax_liability: Decimal,
    credits: TaxCreditBreakdown,
    refund_due: Decimal,
    tax_payable: Decimal,
) -> list[TaxComputationStep]:
    return [
        TaxComputationStep(
            step_key="gross_total_income",
            label="Gross total income",
            amount=income.gross_total_income,
            formula="Salary + house property + business/profession + capital gains + other sources",
        ),
        TaxComputationStep(
            step_key="taxable_income",
            label="Taxable income",
            amount=taxable_income,
            formula="Gross total income - standard deduction - allowed deductions",
        ),
        TaxComputationStep(
            step_key="slab_tax",
            label="Tax before rebate",
            amount=tax_before_rebate,
            formula="Taxable income applied to configured slab rates",
        ),
        TaxComputationStep(
            step_key="rebate",
            label="Rebate",
            amount=rebate,
            formula="Configured rebate threshold and limit",
        ),
        TaxComputationStep(
            step_key="surcharge",
            label="Surcharge",
            amount=surcharge,
            formula="Configured surcharge rules",
        ),
        TaxComputationStep(
            step_key="cess",
            label="Cess",
            amount=cess,
            formula="Configured cess rate on tax after rebate and surcharge",
        ),
        TaxComputationStep(
            step_key="credits",
            label="Tax credits",
            amount=credits.total_credits,
            formula="TDS + TCS + advance tax + self-assessment tax",
        ),
        TaxComputationStep(
            step_key="settlement",
            label="Refund or payable",
            amount=refund_due if refund_due else tax_payable,
            formula="Total tax liability compared with total credits",
        ),
        TaxComputationStep(
            step_key="total_tax_liability",
            label="Total tax liability",
            amount=total_tax_liability,
            formula="Tax after rebate + surcharge + cess",
        ),
        TaxComputationStep(
            step_key="allowed_deductions",
            label="Allowed deductions",
            amount=deductions.allowed_total,
            formula="Deduction claims capped by selected regime config",
        ),
    ]

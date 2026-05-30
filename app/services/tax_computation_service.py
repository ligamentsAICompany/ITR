"""Deterministic tax computation orchestration."""

from typing import cast
from uuid import uuid4

from app.models.decision import ITRDecisionResponse
from app.models.tax_computation import (
    TaxComputationResult,
    TaxComputationWarning,
    TaxExplanationResponse,
    TaxRegime,
)
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport, ValidationSeverity, ValidationStatus
from app.services.tax_computation_rules import (
    compute_cess,
    compute_deductions,
    compute_income_breakdown,
    compute_rebate,
    compute_refund_or_payable,
    compute_slab_tax,
    compute_surcharge,
    compute_tax_credits,
    compute_taxable_income,
    round_money,
)
from itr_engine.legal_packs import TaxComputationPack, TaxRegimeConfig, legal_pack_for_profile


class MissingTaxConfigError(ValueError):
    """Raised when legal-pack tax constants are absent for deterministic computation."""


class TaxComputationService:
    def compute(
        self,
        *,
        profile: CanonicalTaxProfile,
        candidate_itr: ITRDecisionResponse,
        validation_report: ValidationReport | None = None,
        selected_regime: TaxRegime | None = None,
    ) -> TaxComputationResult:
        pack = self._tax_pack_for_profile(profile)
        regime_id = selected_regime or cast(TaxRegime, pack.default_regime)
        regime = self._regime_config(pack, regime_id)

        income, income_warnings = compute_income_breakdown(profile, regime)
        deductions, deduction_warnings = compute_deductions(profile.deductions.section_claims, regime)
        taxable_income = compute_taxable_income(income, deductions)
        tax_before_rebate = compute_slab_tax(taxable_income, regime.slabs)
        rebate = compute_rebate(taxable_income, tax_before_rebate, regime)
        tax_after_rebate = round_money(max(tax_before_rebate - rebate, 0))
        surcharge = compute_surcharge(tax_after_rebate, regime)
        cess = compute_cess(tax_after_rebate + surcharge, regime)
        total_tax_liability = round_money(tax_after_rebate + surcharge + cess)
        credits = compute_tax_credits(profile)
        refund_due, tax_payable = compute_refund_or_payable(total_tax_liability, credits)
        validation_warnings, is_preview = self._validation_warnings(validation_report)

        warnings = [*validation_warnings, *income_warnings, *deduction_warnings]
        steps = [
            *self._base_steps(
                income=income,
                deductions=deductions,
                taxable_income=taxable_income,
                tax_before_rebate=tax_before_rebate,
                rebate=rebate,
                surcharge=surcharge,
                cess=cess,
                total_tax_liability=total_tax_liability,
                credits=credits,
                refund_due=refund_due,
                tax_payable=tax_payable,
            )
        ]
        return TaxComputationResult(
            computation_id=f"tax-{uuid4().hex}",
            assessment_year=pack.assessment_year,
            previous_year=pack.previous_year,
            selected_regime=regime_id,
            regime_label=regime.label,
            default_regime=cast(TaxRegime, pack.default_regime),
            candidate_itr=candidate_itr.candidate_itr,
            is_preview=is_preview,
            income=income,
            deductions=deductions,
            taxable_income=taxable_income,
            tax_before_rebate=tax_before_rebate,
            rebate=rebate,
            surcharge=surcharge,
            cess=cess,
            total_tax_liability=total_tax_liability,
            credits=credits,
            refund_due=refund_due,
            tax_payable=tax_payable,
            warnings=warnings,
            steps=steps,
        )

    def explain(self, result: TaxComputationResult) -> TaxExplanationResponse:
        settlement = (
            f"refund due is {result.refund_due}"
            if result.refund_due
            else f"tax payable is {result.tax_payable}"
        )
        warning_text = (
            " Warnings: " + " ".join(warning.message for warning in result.warnings)
            if result.warnings
            else ""
        )
        explanation = (
            f"Tax computation {result.computation_id} used the {result.regime_label}. "
            f"Gross total income is {result.income.gross_total_income}, taxable income is {result.taxable_income}, "
            f"tax before rebate is {result.tax_before_rebate}, rebate is {result.rebate}, "
            f"total tax liability is {result.total_tax_liability}, credits are {result.credits.total_credits}, and {settlement}."
            f"{warning_text}"
        )
        return TaxExplanationResponse(
            grounded_computation_id=result.computation_id,
            explanation=explanation,
            warnings=result.warnings,
        )

    def _tax_pack_for_profile(self, profile: CanonicalTaxProfile) -> TaxComputationPack:
        legal_pack = legal_pack_for_profile(profile.model_dump(mode="json", exclude_none=True))
        tax_pack = getattr(legal_pack, "tax_computation", None)
        if tax_pack is None:
            raise MissingTaxConfigError("Missing tax computation config for legal pack")
        if tax_pack.default_regime not in {"old", "new"}:
            raise MissingTaxConfigError("Missing valid default tax regime in legal pack")
        return tax_pack

    def _regime_config(self, pack: TaxComputationPack, regime_id: TaxRegime) -> TaxRegimeConfig:
        regime = pack.old_regime if regime_id == "old" else pack.new_regime
        if regime is None:
            raise MissingTaxConfigError(f"Missing {regime_id} regime tax config in legal pack")
        if not regime.slabs:
            raise MissingTaxConfigError(f"Missing slab config for {regime_id} regime")
        if regime.cess_rate is None:
            raise MissingTaxConfigError(f"Missing cess config for {regime_id} regime")
        return regime

    def _validation_warnings(
        self,
        validation_report: ValidationReport | None,
    ) -> tuple[list[TaxComputationWarning], bool]:
        if validation_report is None:
            return [], False

        warnings: list[TaxComputationWarning] = []
        is_preview = False
        if validation_report.overall_status == ValidationStatus.FAILED:
            is_preview = True
            warnings.append(
                TaxComputationWarning(
                    code="VALIDATION_FAILED_PREVIEW_ONLY",
                    message="Validation failed, so this computation is a preview and must not be treated as final.",
                )
            )
        if validation_report.overall_status == ValidationStatus.NEEDS_REVIEW:
            warnings.append(
                TaxComputationWarning(
                    code="VALIDATION_NEEDS_REVIEW",
                    message="Validation needs review; computation may change after review.",
                )
            )
        if validation_report.conflicts:
            warnings.append(
                TaxComputationWarning(
                    code="VALIDATION_CONFLICTS_PRESENT",
                    message="Validation conflicts are present; computation result may change after reconciliation.",
                )
            )
        if any(issue.severity == ValidationSeverity.HIGH for issue in validation_report.issues):
            warnings.append(
                TaxComputationWarning(
                    code="HIGH_SEVERITY_VALIDATION_ISSUE",
                    message="High-severity validation issue present; review before relying on computation.",
                )
            )
        return warnings, is_preview

    def _base_steps(self, **kwargs):
        from app.services.tax_computation_rules import build_computation_steps

        return build_computation_steps(**kwargs)

import { TaxBreakdownCard, formatIndianCurrency } from "./TaxBreakdownCard";
import { TaxComputationSteps } from "./TaxComputationSteps";
import { TaxWarningsPanel } from "./TaxWarningsPanel";
import type { TaxComputationResult, ValidationReport } from "@/types/itr";

export function TaxComputationPanel({
  result,
  validationReport,
}: {
  result: TaxComputationResult | null;
  validationReport: ValidationReport | null;
}) {
  if (!result) {
    return (
      <section className="rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#0369a1]">Tax computation</p>
        <p className="mt-3 text-sm leading-6 text-gray-600">
          Run the workflow to compute deterministic tax after ITR recommendation and validation.
        </p>
      </section>
    );
  }

  const settlementLabel = result.refund_due > 0 ? "Refund due" : "Tax payable";
  const settlementValue = result.refund_due > 0 ? result.refund_due : result.tax_payable;

  return (
    <section className="fade-in rounded-2xl border border-sky-200 bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#0369a1]">Tax computation</p>
          <h2 className="mt-1 text-2xl font-semibold text-[#111827]">{result.regime_label}</h2>
          <p className="mt-2 text-sm leading-6 text-gray-600">
            Deterministic computation for AY {result.assessment_year}. Candidate ITR remains {result.candidate_itr}.
          </p>
        </div>
        <div className="rounded-2xl bg-sky-50 px-5 py-4 text-center text-sky-900">
          <p className="text-xs font-semibold uppercase tracking-[0.16em]">Selected regime</p>
          <p className="text-2xl font-semibold capitalize">{result.selected_regime}</p>
        </div>
      </div>

      {result.is_preview ? (
        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-medium text-amber-950">
          Preview only. Validation failed or needs review, so this result should not be relied on as final.
        </div>
      ) : null}

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <TaxBreakdownCard label="Gross total income" value={result.income.gross_total_income} />
        <TaxBreakdownCard label="Deductions" value={result.deductions.allowed_total} />
        <TaxBreakdownCard label="Taxable income" value={result.taxable_income} />
        <TaxBreakdownCard label="Tax before rebate" value={result.tax_before_rebate} />
        <TaxBreakdownCard label="Rebate" value={result.rebate} tone="credit" />
        <TaxBreakdownCard label="Surcharge" value={result.surcharge} />
        <TaxBreakdownCard label="Cess" value={result.cess} />
        <TaxBreakdownCard label="Liability" value={result.total_tax_liability} />
        <TaxBreakdownCard label="Credits" value={result.credits.total_credits} tone="credit" />
        <TaxBreakdownCard
          label={settlementLabel}
          value={settlementValue}
          tone={result.refund_due > 0 ? "credit" : "payable"}
        />
      </div>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
        <p>
          Salary {formatIndianCurrency(result.income.salary_income)}, standard deduction{" "}
          {formatIndianCurrency(result.income.standard_deduction)}, other sources{" "}
          {formatIndianCurrency(result.income.other_sources_income)}, house property{" "}
          {formatIndianCurrency(result.income.house_property_income)}, business/profession{" "}
          {formatIndianCurrency(result.income.business_profession_income)}, capital gains{" "}
          {formatIndianCurrency(result.income.capital_gains_income)}.
        </p>
      </div>

      <TaxWarningsPanel warnings={result.warnings} validationReport={validationReport} isPreview={result.is_preview} />
      <TaxComputationSteps steps={result.steps} />
    </section>
  );
}

import { formatIndianCurrency } from "./TaxBreakdownCard";
import type { TaxComputationStep } from "@/types/itr";

export function TaxComputationSteps({ steps }: { steps: TaxComputationStep[] }) {
  if (!steps.length) {
    return null;
  }

  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold text-[#111827]">Computation steps</h3>
      <ol className="mt-3 space-y-3">
        {steps.map((step) => (
          <li key={step.step_key} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-900">{step.label}</p>
                <p className="mt-1 text-xs leading-5 text-slate-600">{step.formula}</p>
              </div>
              <span className="text-sm font-semibold tabular-nums text-slate-900">
                {formatIndianCurrency(step.amount)}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

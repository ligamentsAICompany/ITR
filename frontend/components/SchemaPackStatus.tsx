import type { ItrExport } from "@/types/itr";

export function SchemaPackStatus({ exportResult }: { exportResult: ItrExport | null }) {
  if (!exportResult) {
    return (
      <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
        Schema pack status appears after export validation.
      </p>
    );
  }

  if (exportResult.status === "not_configured") {
    return (
      <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        No active schema pack is configured for {exportResult.candidate_itr} / {exportResult.assessment_year}. Export validation is safely blocked.
      </p>
    );
  }

  return (
    <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
      Schema pack configured for {exportResult.candidate_itr} / {exportResult.assessment_year}.
    </p>
  );
}

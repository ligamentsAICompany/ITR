import type { ValidationIssue } from "@/types/itr";

const severityStyles: Record<string, string> = {
  critical: "border-red-300 bg-red-50 text-red-900",
  high: "border-orange-300 bg-orange-50 text-orange-950",
  medium: "border-amber-300 bg-amber-50 text-amber-950",
  low: "border-slate-300 bg-slate-50 text-slate-800",
  info: "border-emerald-300 bg-emerald-50 text-emerald-900",
};

export function ValidationIssueCard({ issue }: { issue: ValidationIssue }) {
  const style = severityStyles[issue.severity] ?? severityStyles.low;

  return (
    <article className={`rounded-xl border p-4 ${style}`}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em]">
            {issue.severity} · {issue.status.replaceAll("_", " ")}
          </p>
          <h3 className="mt-1 text-base font-semibold">{issue.title}</h3>
        </div>
        {issue.blocks_filing_package ? (
          <span className="w-fit rounded-full bg-white/70 px-3 py-1 text-xs font-semibold">
            Filing package blocked
          </span>
        ) : null}
      </div>

      <p className="mt-3 text-sm leading-6">{issue.message}</p>
      <p className="mt-2 text-sm font-medium">Suggested action: {issue.recommendation}</p>

      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <span>Field: {issue.field_path}</span>
        {issue.source_documents.length ? <span>Evidence: {issue.source_documents.join(", ")}</span> : null}
      </div>
    </article>
  );
}

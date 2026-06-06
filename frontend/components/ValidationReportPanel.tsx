import { ReconciliationConflictPanel } from "./ReconciliationConflictPanel";
import { ValidationIssueCard } from "./ValidationIssueCard";
import type { ValidationIssue, ValidationReport } from "@/types/itr";

const severityRank: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
};

export function sortValidationIssues(issues: ValidationIssue[]): ValidationIssue[] {
  return [...issues].sort((left, right) => severityRank[left.severity] - severityRank[right.severity]);
}

export function ValidationReportPanel({ report }: { report: ValidationReport | null }) {
  if (!report) {
    return (
      <section className="rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#0f766e]">Validation report</p>
        <p className="mt-3 text-sm leading-6 text-gray-600">
          Run the workflow to reconcile reviewed evidence against the canonical profile. This does not replace the ITR
          recommendation.
        </p>
      </section>
    );
  }

  const sortedIssues = sortValidationIssues(report.issues);
  const hasCritical = sortedIssues.some((issue) => issue.severity === "critical");

  return (
    <section className="fade-in rounded-2xl border border-[#99f6e4] bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#0f766e]">Validation report</p>
          <h2 className="mt-1 text-2xl font-semibold capitalize text-[#111827]">
            {report.overall_status.replaceAll("_", " ")}
          </h2>
          <p className="mt-2 text-sm leading-6 text-gray-600">
            Deterministic evidence checks only. Extracted values remain untrusted unless you approve them.
          </p>
        </div>
        <div className="rounded-2xl bg-[#ecfdf5] px-5 py-4 text-center text-[#065f46]">
          <p className="text-xs font-semibold uppercase tracking-[0.16em]">Readiness</p>
          <p className="text-3xl font-semibold">{report.readiness_score}</p>
        </div>
      </div>

      {hasCritical ? (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800">
          Critical validation issue present. Do not prepare a filing package until resolved.
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
          No critical blocker found. Needs CA review when high-risk findings are present.
        </div>
      )}

      {report.missing_fields.length ? (
        <div className="mt-5">
          <h3 className="text-sm font-semibold text-[#111827]">Missing fields</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {report.missing_fields.map((field) => (
              <span key={field} className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
                {field}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {report.warnings.length ? (
        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          {report.warnings.join(" ")}
        </div>
      ) : null}

      <div className="mt-5 space-y-3">
        {sortedIssues.length ? (
          sortedIssues.map((issue) => <ValidationIssueCard key={issue.issue_id} issue={issue} />)
        ) : (
          <p className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
            Validation passed with no deterministic mismatches.
          </p>
        )}
      </div>

      <div className="mt-5">
        <ReconciliationConflictPanel conflicts={report.conflicts} />
      </div>
    </section>
  );
}

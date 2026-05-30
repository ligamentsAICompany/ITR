import type { FilingReadinessResult, FilingSubmission } from "@/types/itr";

const filingWarning = "This action has not submitted anything to the Income Tax Department unless provider mode is live and submission succeeds.";
const mockWarning = "This is a mock/sandbox filing workflow for testing. It does not file a real tax return.";

export function FilingSubmissionPanel({
  submission,
  readiness,
  error,
  loading,
  onCreate,
  onSubmit,
  onStatusCheck,
}: {
  submission: FilingSubmission | null;
  readiness: FilingReadinessResult | null;
  error: string | null;
  loading: boolean;
  onCreate: () => void;
  onSubmit: () => void;
  onStatusCheck: () => void;
}) {
  const status = submission?.submission_status.replaceAll("_", " ") ?? "not created";
  const canSubmit = Boolean(submission && readiness?.ready);
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-700">Filing submission</p>
      <h3 className="mt-1 text-xl font-semibold capitalize text-[#111827]">{status}</h3>
      <p className="mt-2 text-sm text-gray-600">{filingWarning}</p>
      {(submission?.provider_mode ?? readiness?.provider_mode) !== "live" ? <p className="mt-1 text-sm text-gray-600">{mockWarning}</p> : null}
      {submission ? <p className="mt-3 text-sm font-semibold capitalize text-slate-900">Provider mode: {submission.provider_mode}</p> : null}
      {error ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded-full bg-slate-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading} onClick={onCreate} type="button">
          Create draft
        </button>
        <button className="rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading || !canSubmit} onClick={onSubmit} type="button">
          Submit through provider
        </button>
        <button className="rounded-full bg-cyan-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading || !submission} onClick={onStatusCheck} type="button">
          Check status
        </button>
      </div>
    </section>
  );
}

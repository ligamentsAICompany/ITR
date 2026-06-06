import type { FilingReadinessResult } from "@/types/itr";

const filingWarning = "This action has not submitted anything to the Income Tax Department unless provider mode is live and submission succeeds.";
const mockWarning = "This is a mock/sandbox filing workflow for testing. It does not file a real tax return.";

export function FilingReadinessPanel({
  readiness,
  loading,
  onCheck,
}: {
  readiness: FilingReadinessResult | null;
  loading: boolean;
  onCheck: () => void;
}) {
  return (
    <section className="fade-in rounded-2xl border border-cyan-200 bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-700">Filing readiness</p>
          <h2 className="mt-1 text-2xl font-semibold capitalize text-[#111827]">
            {readiness?.ready ? "Ready for gated submission" : "Submission gate not ready"}
          </h2>
          <p className="mt-2 text-sm leading-6 text-gray-600">{filingWarning}</p>
          {readiness?.provider_mode !== "live" ? <p className="mt-1 text-sm leading-6 text-gray-600">{mockWarning}</p> : null}
        </div>
        <button
          type="button"
          onClick={onCheck}
          disabled={loading}
          className="rounded-full bg-cyan-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-cyan-800 disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          {loading ? "Checking..." : "Check readiness"}
        </button>
      </div>
      {readiness ? (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <Metric label="Provider mode" value={readiness.provider_mode} />
            <Metric label="Blockers" value={`${readiness.blockers.length}`} />
            <Metric label="Required actions" value={`${readiness.required_actions.length}`} />
          </div>
          <List title="Blockers" items={readiness.blockers} empty="No readiness blockers." />
          <List title="Required actions" items={readiness.required_actions} empty="No further actions required." />
          <List title="Warnings" items={readiness.warnings} empty="No provider warnings." />
        </>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-cyan-50 p-4 text-cyan-950">
      <p className="text-xs font-semibold uppercase tracking-[0.16em]">{label}</p>
      <p className="mt-1 text-xl font-semibold capitalize">{label === "Provider mode" ? `Provider mode: ${value}` : value}</p>
    </div>
  );
}

function List({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
      <p className="font-semibold text-slate-900">{title}</p>
      {items.length ? (
        <ul className="mt-2 space-y-1">
          {items.map((item) => (
            <li key={item} className="capitalize">
              {item.replaceAll("_", " ")}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2">{empty}</p>
      )}
    </div>
  );
}

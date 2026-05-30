import type { FilingReadinessResult, FilingSubmission } from "@/types/itr";
import { FilingProviderModeBadge } from "./FilingProviderModeBadge";

const liveDisclaimer = "Live filing is disabled unless explicitly enabled and approved.";

export function ProviderStatusPanel({
  readiness,
  submission,
  everificationSupported,
  acknowledgementAvailable,
}: {
  readiness: FilingReadinessResult | null;
  submission: FilingSubmission | null;
  everificationSupported: boolean;
  acknowledgementAvailable: boolean;
}) {
  const provider = submission?.provider ?? readiness?.provider ?? "mock";
  const mode = submission?.provider_mode ?? readiness?.provider_mode ?? "mock";
  const missingConfig = readiness?.blockers.includes("provider_not_configured") ?? false;
  const liveDisabled = readiness?.blockers.includes("live_filing_disabled") || (mode === "live" && provider !== "mock");
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-700">Provider diagnostics</p>
          <h3 className="mt-1 text-xl font-semibold text-[#111827]">ERI readiness foundation</h3>
        </div>
        <FilingProviderModeBadge provider={provider} mode={mode} liveAllowed={!liveDisabled} />
      </div>
      <p className="mt-3 text-sm font-semibold text-slate-700">{liveDisclaimer}</p>
      {missingConfig ? <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Provider configuration missing. Configure ERI values through Secret Manager before sandbox or live filing.</p> : null}
      {liveDisabled ? <p className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">Live filing disabled. Submission is blocked until explicit approval and configuration are present.</p> : null}
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">Last status check</dt>
          <dd className="mt-1 text-slate-600">{submission?.last_checked_at ? new Date(submission.last_checked_at).toLocaleString() : "Not checked yet"}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">E-verification capability</dt>
          <dd className="mt-1 text-slate-600">{everificationSupported ? "E-verification supported" : "E-verification unsupported"}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">Acknowledgement availability</dt>
          <dd className="mt-1 text-slate-600">{acknowledgementAvailable ? "Acknowledgement available" : "Acknowledgement unavailable"}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">Provider status</dt>
          <dd className="mt-1 capitalize text-slate-600">{submission?.submission_status?.replaceAll("_", " ") ?? "Draft not created"}</dd>
        </div>
      </dl>
    </section>
  );
}

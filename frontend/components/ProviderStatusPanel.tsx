import type { FilingReadinessResult, FilingSubmission, ProviderDiagnostics } from "@/types/itr";
import { FilingProviderModeBadge } from "./FilingProviderModeBadge";

const liveDisclaimer = "Live filing requires approved credentials, legal approval, and explicit enablement.";

export function ProviderStatusPanel({
  readiness,
  submission,
  diagnostics,
  everificationSupported,
  acknowledgementAvailable,
}: {
  readiness: FilingReadinessResult | null;
  submission: FilingSubmission | null;
  diagnostics?: ProviderDiagnostics | null;
  everificationSupported: boolean;
  acknowledgementAvailable: boolean;
}) {
  const provider = diagnostics?.provider ?? submission?.provider ?? readiness?.provider ?? "mock";
  const mode = diagnostics?.mode ?? submission?.provider_mode ?? readiness?.provider_mode ?? "mock";
  const missingConfig = diagnostics?.configured === false || readiness?.blockers.includes("provider_not_configured") || false;
  const liveDisabled = diagnostics ? !diagnostics.live_filing_enabled && mode === "live" : readiness?.blockers.includes("live_filing_disabled") || (mode === "live" && provider !== "mock");
  const supportedOperations = diagnostics?.supported_operations ?? [];
  const contractStatus = diagnostics?.last_contract_test?.status ?? "not run";
  const sandboxContractStatus = diagnostics?.sandbox_contract_status ?? contractStatus;
  const safeReadiness = diagnostics?.safe_readiness ?? (missingConfig ? "not_configured" : "configured");
  const lastStatusCheck = diagnostics?.last_status_check ?? submission?.last_checked_at;
  const secretBackend = diagnostics?.secret_backend?.replaceAll("_", " ") ?? "env";
  const capabilities = diagnostics?.provider_capabilities ?? supportedOperations;
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
      {mode === "sandbox" ? <p className="mt-3 rounded-xl border border-cyan-200 bg-cyan-50 p-3 text-sm font-semibold text-cyan-900">Sandbox submission only. This is not a real tax filing.</p> : null}
      {missingConfig ? <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Provider configuration missing. Configure ERI values through Secret Manager before sandbox or live filing.</p> : null}
      {liveDisabled ? <p className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">Live filing disabled. Submission is blocked until explicit approval and configuration are present.</p> : null}
      {diagnostics?.live_blocked_reason ? <p className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">Live disabled reason: {diagnostics.live_blocked_reason}</p> : null}
      {diagnostics?.retryable_provider_error ? <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{diagnostics.retryable_provider_error}</p> : null}
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">Secret backend</dt>
          <dd className="mt-1 capitalize text-slate-600">{secretBackend}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">Sandbox configured</dt>
          <dd className="mt-1 text-slate-600">{diagnostics?.sandbox_configured ? "Sandbox configured" : "Sandbox not configured"}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">Sandbox calls</dt>
          <dd className="mt-1 text-slate-600">{diagnostics?.sandbox_calls_allowed ? "Sandbox calls enabled" : "Sandbox calls disabled"}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">Sandbox contract</dt>
          <dd className="mt-1 capitalize text-slate-600">{sandboxContractStatus.replaceAll("_", " ")}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">Last status check</dt>
          <dd className="mt-1 text-slate-600">{lastStatusCheck ? new Date(lastStatusCheck).toLocaleString() : "Not checked yet"}</dd>
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
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">Safe readiness</dt>
          <dd className="mt-1 capitalize text-slate-600">{safeReadiness.replaceAll("_", " ")}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <dt className="font-semibold text-slate-900">Contract test</dt>
          <dd className="mt-1 capitalize text-slate-600">{contractStatus.replaceAll("_", " ")}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-3 sm:col-span-2">
          <dt className="font-semibold text-slate-900">Supported operations</dt>
          <dd className="mt-1 text-slate-600">{capabilities.length ? capabilities.map((item) => item.replaceAll("_", " ")).join(", ") : "No provider operations configured"}</dd>
        </div>
        {diagnostics?.safe_missing_config?.length ? (
          <div className="rounded-xl bg-slate-50 p-3 sm:col-span-2">
            <dt className="font-semibold text-slate-900">Safe missing config</dt>
            <dd className="mt-1 text-slate-600">{diagnostics.safe_missing_config.join(", ")}</dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}

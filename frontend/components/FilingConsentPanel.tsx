import type { FilingConsent } from "@/types/itr";

export function FilingConsentPanel({
  consent,
  error,
  loading,
  onRequest,
  onGrant,
  onRevoke,
}: {
  consent: FilingConsent | null;
  error: string | null;
  loading: boolean;
  onRequest: () => void;
  onGrant: () => void;
  onRevoke: () => void;
}) {
  const status = consent?.consent_status.replaceAll("_", " ") ?? "not requested";
  return (
    <section className="rounded-2xl border border-amber-200 bg-white p-6 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-700">Taxpayer consent</p>
      <h3 className="mt-1 text-xl font-semibold capitalize text-[#111827]">Consent {status}</h3>
      <p className="mt-2 text-sm text-gray-600">Consent is specific to this filing package and export. It can be revoked before submission.</p>
      {error ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded-full bg-amber-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading} onClick={onRequest} type="button">
          Request consent
        </button>
        <button className="rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading || !consent || consent.consent_status === "granted"} onClick={onGrant} type="button">
          Grant consent
        </button>
        <button className="rounded-full bg-slate-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading || !consent || consent.consent_status !== "granted"} onClick={onRevoke} type="button">
          Revoke consent
        </button>
      </div>
    </section>
  );
}

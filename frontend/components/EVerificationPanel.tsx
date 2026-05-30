import type { FilingSubmission } from "@/types/itr";

export function EVerificationPanel({
  submission,
  loading,
  onInitiate,
  onRefresh,
}: {
  submission: FilingSubmission | null;
  loading: boolean;
  onInitiate: () => void;
  onRefresh: () => void;
}) {
  const status = submission?.everification_status.replaceAll("_", " ") ?? "not started";
  return (
    <section className="rounded-2xl border border-teal-200 bg-white p-6 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-teal-700">E-verification</p>
      <h3 className="mt-1 text-xl font-semibold capitalize text-[#111827]">{status}</h3>
      <p className="mt-2 text-sm text-gray-600">E-verification can only be initiated after provider-confirmed submission.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded-full bg-teal-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading || !submission?.provider_reference_id} onClick={onInitiate} type="button">
          Initiate e-verification
        </button>
        <button className="rounded-full bg-slate-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading || !submission} onClick={onRefresh} type="button">
          Refresh e-verification
        </button>
      </div>
    </section>
  );
}

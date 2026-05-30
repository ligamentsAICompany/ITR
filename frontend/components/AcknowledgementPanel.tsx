import type { Acknowledgement } from "@/types/itr";

export function AcknowledgementPanel({
  acknowledgement,
  error,
  loading,
  onRefresh,
}: {
  acknowledgement: Acknowledgement | null;
  error: string | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <section className="rounded-2xl border border-lime-200 bg-white p-6 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-lime-700">Acknowledgement</p>
      <h3 className="mt-1 text-xl font-semibold text-[#111827]">
        {acknowledgement ? acknowledgement.acknowledgement_number : "Not available"}
      </h3>
      <p className="mt-2 text-sm text-gray-600">An acknowledgement is shown only when the provider returns one.</p>
      {error ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div> : null}
      <button className="mt-4 rounded-full bg-lime-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading} onClick={onRefresh} type="button">
        Refresh acknowledgement
      </button>
    </section>
  );
}

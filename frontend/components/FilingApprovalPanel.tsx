import type { FilingApproval } from "@/types/itr";

export function FilingApprovalPanel({
  approval,
  canApprove,
  canRequest = true,
  guardMessage,
  error,
  loading,
  onRequest,
  onApprove,
  onReject,
}: {
  approval: FilingApproval | null;
  canApprove: boolean;
  canRequest?: boolean;
  guardMessage?: string | null;
  error: string | null;
  loading: boolean;
  onRequest: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const status = approval?.approval_status.replaceAll("_", " ") ?? "not requested";
  return (
    <section className="rounded-2xl border border-violet-200 bg-white p-6 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-violet-700">Human approval gate</p>
      <h3 className="mt-1 text-xl font-semibold capitalize text-[#111827]">Approval {status}</h3>
      <p className="mt-2 text-sm text-gray-600">Reviewer/admin approval is required when the case needs review. Approval never mutates the export payload.</p>
      {!canRequest && guardMessage ? (
        <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{guardMessage}</p>
      ) : null}
      {error ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded-full bg-violet-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading || !canRequest} onClick={onRequest} type="button">
          Request approval
        </button>
        <button className="rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading || !approval || !canApprove || approval.approval_status !== "pending"} onClick={onApprove} type="button">
          Approve
        </button>
        <button className="rounded-full bg-rose-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300" disabled={loading || !approval || !canApprove || approval.approval_status !== "pending"} onClick={onReject} type="button">
          Reject
        </button>
      </div>
    </section>
  );
}

import type { DraftItrPayload } from "@/types/itr";

export function DraftItrPayloadPreview({ payload }: { payload: DraftItrPayload | null }) {
  if (!payload) {
    return null;
  }

  return (
    <details className="mt-5 rounded-2xl border border-slate-200 bg-slate-950 p-4 text-sm text-slate-100">
      <summary className="cursor-pointer font-semibold">Draft ITR payload preview</summary>
      <pre className="mt-4 max-h-80 overflow-auto text-xs leading-5">
        {JSON.stringify(payload, null, 2)}
      </pre>
    </details>
  );
}

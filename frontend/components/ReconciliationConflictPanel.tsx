import type { ReconciliationConflict } from "@/types/itr";

export function ReconciliationConflictPanel({ conflicts }: { conflicts: ReconciliationConflict[] }) {
  if (conflicts.length === 0) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-orange-200 bg-orange-50 p-5 text-sm text-orange-950">
      <h3 className="text-base font-semibold">Reconciliation conflicts</h3>
      <div className="mt-4 space-y-3">
        {conflicts.map((conflict) => (
          <div key={`${conflict.field_path}-${conflict.evidence_refs.join(",")}`} className="rounded-xl bg-white p-4">
            <p className="font-semibold">{conflict.field_path}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-500">Profile value</p>
                <p className="mt-1 text-gray-900">{formatValue(conflict.profile_value)}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-500">Extracted value</p>
                <p className="mt-1 text-gray-900">{formatValue(conflict.extracted_value)}</p>
              </div>
            </div>
            <p className="mt-3 text-xs text-gray-600">
              Evidence links: {[...conflict.source_documents, ...conflict.evidence_refs].join(", ") || "None"}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Not provided";
  }
  return String(value);
}

import type { OfficialSchemaValidationResult } from "@/types/itr";

export function ItrSchemaValidationErrors({ result }: { result: OfficialSchemaValidationResult | null }) {
  if (!result || (result.errors.length === 0 && result.warnings.length === 0)) {
    return null;
  }

  return (
    <div className="mt-5 space-y-3">
      {[...result.errors, ...result.warnings].map((item, index) => (
        <div key={`${item.code}-${item.field_path ?? index}`} className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <p className="font-semibold">{item.code}</p>
            <span className="text-xs font-semibold uppercase tracking-[0.14em]">{item.severity}</span>
          </div>
          <p className="mt-1 leading-6">{item.message}</p>
          {item.field_path ? <p className="mt-1 text-xs text-amber-800">Field: {item.field_path}</p> : null}
        </div>
      ))}
    </div>
  );
}

import type { ProviderError } from "@/types/itr";

export function ProviderErrorPanel({ error }: { error: ProviderError | null }) {
  if (!error) {
    return null;
  }
  const tone = error.severity === "critical" || error.severity === "error" ? "border-red-200 bg-red-50 text-red-900" : "border-amber-200 bg-amber-50 text-amber-900";
  return (
    <section className={`rounded-2xl border p-4 text-sm ${tone}`}>
      <p className="font-semibold">Provider error: {error.code.replaceAll("_", " ").toLowerCase()}</p>
      <p className="mt-1">{error.safe_message}</p>
      <p className="mt-2 text-xs font-semibold uppercase tracking-[0.14em]">{error.retryable ? "Retryable provider error" : "Manual review required"}</p>
    </section>
  );
}

import type { FilingProviderName, ProviderMode } from "@/types/itr";

export function FilingProviderModeBadge({
  provider,
  mode,
  liveAllowed = false,
}: {
  provider: FilingProviderName | string;
  mode: ProviderMode;
  liveAllowed?: boolean;
}) {
  const tone = mode === "live" ? "border-red-300 bg-red-50 text-red-800" : mode === "sandbox" ? "border-amber-300 bg-amber-50 text-amber-900" : "border-slate-300 bg-slate-50 text-slate-700";
  return (
    <div className={`inline-flex flex-wrap items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${tone}`}>
      <span>Provider {providerLabel(provider)}</span>
      <span>Mode {mode}</span>
      {mode === "live" && !liveAllowed ? <span>Live filing disabled</span> : null}
    </div>
  );
}

function providerLabel(provider: FilingProviderName | string): string {
  return provider.replaceAll("_", " ");
}

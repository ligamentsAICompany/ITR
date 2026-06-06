type TaxBreakdownCardProps = {
  label: string;
  value: number;
  tone?: "neutral" | "credit" | "payable";
  detail?: string;
};

export function formatIndianCurrency(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 0,
    style: "currency",
    currency: "INR",
  }).format(value);
}

export function TaxBreakdownCard({ label, value, tone = "neutral", detail }: TaxBreakdownCardProps) {
  const toneClass =
    tone === "credit"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
      : tone === "payable"
        ? "border-amber-200 bg-amber-50 text-amber-950"
        : "border-slate-200 bg-slate-50 text-slate-900";

  return (
    <div className={`rounded-2xl border p-4 ${toneClass}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.16em] opacity-75">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{formatIndianCurrency(value)}</p>
      {detail ? <p className="mt-2 text-xs leading-5 opacity-75">{detail}</p> : null}
    </div>
  );
}

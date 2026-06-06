import type { FilingPackageStatus, FilingPackageWarning } from "@/types/itr";

export function FilingPackageWarnings({
  warnings,
  status,
}: {
  warnings: FilingPackageWarning[];
  status: FilingPackageStatus;
}) {
  if (!warnings.length && status !== "blocked") {
    return null;
  }

  return (
    <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
      <p className="font-semibold">
        {status === "blocked" ? "Blocked package warning" : "Package warnings"}
      </p>
      <ul className="mt-2 list-disc space-y-2 pl-5">
        {warnings.map((warning) => (
          <li key={warning.warning_id}>
            <span className="font-medium capitalize">{warning.severity}</span>: {warning.message}{" "}
            <span className="text-amber-800">Recommendation: {warning.recommendation}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

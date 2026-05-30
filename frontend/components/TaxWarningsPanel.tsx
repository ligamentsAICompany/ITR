import type { TaxComputationWarning, ValidationReport } from "@/types/itr";

export function TaxWarningsPanel({
  warnings,
  validationReport,
  isPreview,
}: {
  warnings: TaxComputationWarning[];
  validationReport: ValidationReport | null;
  isPreview: boolean;
}) {
  const validationMessages = validationWarnings(validationReport, isPreview);
  const allWarnings = [
    ...validationMessages,
    ...warnings.map((warning) => `${warning.code}: ${warning.message}`),
  ];

  if (!allWarnings.length) {
    return null;
  }

  return (
    <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
      <p className="font-semibold">Tax computation warnings</p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {allWarnings.map((warning) => (
          <li key={warning}>{warning}</li>
        ))}
      </ul>
    </div>
  );
}

function validationWarnings(report: ValidationReport | null, isPreview: boolean): string[] {
  if (!report) {
    return [];
  }

  const warnings: string[] = [];
  if (isPreview || report.overall_status === "failed") {
    warnings.push("Validation failed; this tax computation is preview-only.");
  }
  if (report.overall_status === "needs_review") {
    warnings.push("Validation needs review; tax output may change after review.");
  }
  if (report.conflicts.length > 0) {
    warnings.push("Validation conflicts are present; computation must not resolve or overwrite them.");
  }
  return warnings;
}

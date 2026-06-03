import { ItrExportArtifacts } from "./ItrExportArtifacts";
import { ItrSchemaValidationErrors } from "./ItrSchemaValidationErrors";
import { SchemaPackStatus } from "./SchemaPackStatus";
import type { FilingPackage, ItrExport, ItrExportArtifact } from "@/types/itr";

export function ItrExportPanel({
  filingPackage,
  itrExport,
  error,
  loading,
  canGenerate,
  onGenerate,
  onDownloadArtifact,
}: {
  filingPackage: FilingPackage | null;
  itrExport: ItrExport | null;
  error: string | null;
  loading: boolean;
  canGenerate: boolean;
  onGenerate: () => void;
  onDownloadArtifact: (artifact: ItrExportArtifact) => void;
}) {
  const status = itrExport?.status.replaceAll("_", " ") ?? "Export not generated";

  return (
    <section className="fade-in rounded-2xl border border-emerald-200 bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700">Official ITR export</p>
          <h2 className="mt-1 text-2xl font-semibold capitalize text-[#111827]">{status}</h2>
          <p className="mt-2 text-sm leading-6 text-gray-600">
            This export has not been submitted to the Income Tax Department.
          </p>
          <p className="mt-1 text-sm leading-6 text-gray-600">
            Schema validation means the payload matched the configured schema pack. It does not mean the return has been filed or accepted.
          </p>
          <p className="mt-1 text-sm leading-6 text-gray-600">
            Synthetic demo schema packs are for demo validation only and are not official government schemas.
          </p>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={!canGenerate || loading}
          className="rounded-full bg-emerald-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          {loading ? "Validating..." : "Generate export"}
        </button>
      </div>

      {!filingPackage ? (
        <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
          Generate a filing package before creating the official-schema export.
        </p>
      ) : null}

      {error ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div> : null}

      <SchemaPackStatus exportResult={itrExport} />

      {itrExport ? (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <Metric label="Candidate ITR" value={itrExport.candidate_itr} />
            <Metric label="Validation" value={itrExport.validation_result.status.replaceAll("_", " ")} />
            <Metric label="Artifacts" value={`${itrExport.artifacts.length}`} />
          </div>
          <ItrSchemaValidationErrors result={itrExport.validation_result} />
          <ItrExportArtifacts artifacts={itrExport.artifacts} onDownloadArtifact={onDownloadArtifact} />
        </>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-emerald-50 p-4 text-emerald-950">
      <p className="text-xs font-semibold uppercase tracking-[0.16em]">{label}</p>
      <p className="mt-1 text-xl font-semibold capitalize">{value}</p>
    </div>
  );
}

import { DraftItrPayloadPreview } from "./DraftItrPayloadPreview";
import { FilingPackageArtifacts } from "./FilingPackageArtifacts";
import { FilingPackageWarnings } from "./FilingPackageWarnings";
import type { DraftItrPayload, FilingPackage, FilingPackageArtifact } from "@/types/itr";

export function FilingPackagePanel({
  filingPackage,
  draftPayload,
  error,
  onGenerate,
  onDownloadArtifact,
  canGenerate,
  loading,
}: {
  filingPackage: FilingPackage | null;
  draftPayload: DraftItrPayload | null;
  error: string | null;
  onGenerate: () => void;
  onDownloadArtifact: (artifact: FilingPackageArtifact) => void;
  canGenerate: boolean;
  loading: boolean;
}) {
  return (
    <section className="fade-in rounded-2xl border border-indigo-200 bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-indigo-700">Filing package</p>
          <h2 className="mt-1 text-2xl font-semibold capitalize text-[#111827]">
            {filingPackage ? filingPackage.status.replaceAll("_", " ") : "Draft package not generated"}
          </h2>
          <p className="mt-2 text-sm leading-6 text-gray-600">
            This is a draft filing package for review. It has not been submitted to the Income Tax Department.
          </p>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={!canGenerate || loading}
          className="rounded-full bg-indigo-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-indigo-800 disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          {loading ? "Generating..." : "Generate filing package"}
        </button>
      </div>

      {!canGenerate ? (
        <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
          Run ITR recommendation, validation, and tax computation before generating a package.
        </p>
      ) : null}

      {error ? (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>
      ) : null}

      {filingPackage ? (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <Metric label="Candidate ITR" value={filingPackage.candidate_itr} />
            <Metric label="Readiness" value={`${filingPackage.readiness_score}`} />
            <Metric label="Artifacts" value={`${filingPackage.artifacts.length}`} />
          </div>
          <FilingPackageWarnings warnings={filingPackage.warnings} status={filingPackage.status} />
          <FilingPackageArtifacts artifacts={filingPackage.artifacts} onDownloadArtifact={onDownloadArtifact} />
          <DraftItrPayloadPreview payload={draftPayload} />
        </>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-indigo-50 p-4 text-indigo-950">
      <p className="text-xs font-semibold uppercase tracking-[0.16em]">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

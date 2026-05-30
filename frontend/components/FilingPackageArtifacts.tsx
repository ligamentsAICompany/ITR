import type { FilingPackageArtifact } from "@/types/itr";

export function FilingPackageArtifacts({
  artifacts,
  onDownloadArtifact,
}: {
  artifacts: FilingPackageArtifact[];
  onDownloadArtifact: (artifact: FilingPackageArtifact) => void;
}) {
  if (!artifacts.length) {
    return null;
  }

  return (
    <div className="mt-5">
      <h3 className="text-sm font-semibold text-[#111827]">Artifacts</h3>
      <div className="mt-3 space-y-3">
        {artifacts.map((artifact) => (
          <div
            key={artifact.artifact_id}
            className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <p className="font-medium text-slate-900">{artifact.filename}</p>
              <p className="mt-1 text-xs text-slate-600">
                {artifact.artifact_type.replaceAll("_", " ")} · {artifact.size} bytes · SHA-256{" "}
                {artifact.sha256.slice(0, 12)}...
              </p>
            </div>
            <button
              type="button"
              onClick={() => onDownloadArtifact(artifact)}
              className="rounded-full border border-[#0369a1] px-4 py-2 text-sm font-semibold text-[#0369a1] transition hover:bg-sky-50"
            >
              Download
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

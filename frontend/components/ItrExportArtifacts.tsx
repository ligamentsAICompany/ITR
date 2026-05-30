import type { ItrExportArtifact } from "@/types/itr";

export function ItrExportArtifacts({
  artifacts,
  onDownloadArtifact,
}: {
  artifacts: ItrExportArtifact[];
  onDownloadArtifact: (artifact: ItrExportArtifact) => void;
}) {
  if (artifacts.length === 0) {
    return null;
  }

  return (
    <div className="mt-5 space-y-3">
      {artifacts.map((artifact) => (
        <div key={artifact.artifact_id} className="flex flex-col gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-950 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-semibold">{artifact.filename}</p>
            <p className="text-xs text-emerald-800">{artifact.size} bytes · {artifact.mime_type}</p>
          </div>
          <button
            type="button"
            onClick={() => onDownloadArtifact(artifact)}
            className="rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800"
          >
            Download official export
          </button>
        </div>
      ))}
    </div>
  );
}

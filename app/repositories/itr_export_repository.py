"""Persistence for official ITR export records and artifacts."""

from datetime import UTC, datetime

from app.core.database import get_json_record, save_json_record
from app.models.itr_export import ItrExport

ITR_EXPORT_CACHE: dict[str, ItrExport] = {}
ITR_EXPORT_ARTIFACT_CACHE: dict[tuple[str, str], bytes] = {}


class ItrExportRepository:
    table = "itr_exports"
    artifact_table = "itr_export_artifacts"

    def save(self, export: ItrExport) -> ItrExport:
        ITR_EXPORT_CACHE[export.export_id] = export
        save_json_record(
            self.table,
            export.export_id,
            export.model_dump(mode="json"),
            export.created_at.isoformat(),
            export.updated_at.isoformat(),
        )
        return export

    def get(self, export_id: str) -> ItrExport | None:
        cached = ITR_EXPORT_CACHE.get(export_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table, export_id)
        if payload is None:
            return None
        export = ItrExport.model_validate(payload)
        ITR_EXPORT_CACHE[export.export_id] = export
        return export

    def save_artifact_content(self, export_id: str, artifact_id: str, content: bytes) -> None:
        ITR_EXPORT_ARTIFACT_CACHE[(export_id, artifact_id)] = content
        now = datetime.now(UTC).isoformat()
        save_json_record(
            self.artifact_table,
            artifact_record_id(export_id, artifact_id),
            {"export_id": export_id, "artifact_id": artifact_id, "content": content.decode("utf-8")},
            now,
            now,
        )

    def get_artifact_content(self, export_id: str, artifact_id: str) -> bytes | None:
        cached = ITR_EXPORT_ARTIFACT_CACHE.get((export_id, artifact_id))
        if cached is not None:
            return cached
        payload = get_json_record(self.artifact_table, artifact_record_id(export_id, artifact_id))
        if payload is None:
            return None
        content = str(payload["content"]).encode("utf-8")
        ITR_EXPORT_ARTIFACT_CACHE[(export_id, artifact_id)] = content
        return content


def artifact_record_id(export_id: str, artifact_id: str) -> str:
    return f"{export_id}:{artifact_id}"

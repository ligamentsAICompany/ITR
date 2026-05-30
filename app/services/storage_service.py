"""Cloud-ready local filesystem storage for uploaded tax documents."""

import hashlib
import json
import re
import uuid
from pathlib import Path

from app.models.document import DocumentRecord, DocumentType


class LocalStorageService:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()

    def save(
        self,
        *,
        content: bytes,
        original_filename: str,
        content_type: str,
        document_type: DocumentType,
    ) -> DocumentRecord:
        document_id = str(uuid.uuid4())
        safe_filename = _safe_filename(original_filename)
        document_dir = self.base_dir / document_id
        document_dir.mkdir(parents=True, exist_ok=True)
        storage_path = document_dir / safe_filename
        storage_path.write_bytes(content)

        record = DocumentRecord(
            document_id=document_id,
            document_type=document_type,
            original_filename=safe_filename,
            safe_filename=safe_filename,
            content_type=content_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            storage_path=str(storage_path),
        )
        (document_dir / "metadata.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return record

    def get(self, document_id: str) -> DocumentRecord:
        metadata_path = self._document_dir(document_id) / "metadata.json"
        return DocumentRecord.model_validate(json.loads(metadata_path.read_text(encoding="utf-8")))

    def update(self, record: DocumentRecord) -> DocumentRecord:
        metadata_path = self._document_dir(record.document_id) / "metadata.json"
        metadata_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return record

    def read_bytes(self, document_id: str) -> bytes:
        record = self.get(document_id)
        storage_path = Path(record.storage_path).resolve()
        if not storage_path.is_relative_to(self.base_dir):
            raise FileNotFoundError("Document not found")
        return storage_path.read_bytes()

    def _document_dir(self, document_id: str) -> Path:
        try:
            uuid.UUID(document_id)
        except ValueError as exc:
            raise FileNotFoundError("Document not found") from exc
        document_dir = (self.base_dir / document_id).resolve()
        if not document_dir.is_relative_to(self.base_dir):
            raise FileNotFoundError("Document not found")
        return document_dir


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "document"
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return f"{safe_stem or 'document'}{suffix}"

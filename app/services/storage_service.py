"""Cloud-ready storage for uploaded tax documents."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings
from app.core.database import get_json_record, save_json_record
from app.models.document import DocumentRecord, DocumentType
from app.services.auth_service import DEMO_ORGANIZATION_ID, DEMO_USER_ID
from app.services.object_storage_service import (
    ObjectStorageService,
    get_object_storage_service,
    make_safe_object_key,
    safe_storage_filename,
)

DOCUMENT_CACHE: dict[str, DocumentRecord] = {}


class DocumentStorageService(Protocol):
    def save(
        self,
        *,
        content: bytes,
        original_filename: str,
        content_type: str,
        document_type: DocumentType,
        owner_user_id: str | None = None,
        organization_id: str | None = None,
        created_by: str | None = None,
    ) -> DocumentRecord:
        ...

    def get(self, document_id: str) -> DocumentRecord:
        ...

    def update(self, record: DocumentRecord) -> DocumentRecord:
        ...

    def read_bytes(self, document_id: str) -> bytes:
        ...


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
        owner_user_id: str | None = None,
        organization_id: str | None = None,
        created_by: str | None = None,
    ) -> DocumentRecord:
        document_id = str(uuid.uuid4())
        safe_filename = safe_storage_filename(original_filename)
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
            owner_user_id=owner_user_id or DEMO_USER_ID,
            organization_id=organization_id or DEMO_ORGANIZATION_ID,
            created_by=created_by or owner_user_id or DEMO_USER_ID,
        )
        (document_dir / "metadata.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
        DOCUMENT_CACHE[document_id] = record
        _save_document_record(record)
        return record

    def get(self, document_id: str) -> DocumentRecord:
        cached = DOCUMENT_CACHE.get(document_id)
        if cached is not None:
            return cached
        payload = get_json_record("documents", document_id)
        if payload is not None:
            record = DocumentRecord.model_validate(payload)
            DOCUMENT_CACHE[record.document_id] = record
            return record
        metadata_path = self._document_dir(document_id) / "metadata.json"
        record = DocumentRecord.model_validate(json.loads(metadata_path.read_text(encoding="utf-8")))
        DOCUMENT_CACHE[record.document_id] = record
        return record

    def update(self, record: DocumentRecord) -> DocumentRecord:
        record = record.model_copy(update={"updated_at": datetime.now(UTC)})
        metadata_path = self._document_dir(record.document_id) / "metadata.json"
        metadata_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        DOCUMENT_CACHE[record.document_id] = record
        _save_document_record(record)
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


class GcsDocumentStorageService:
    def __init__(self, object_storage: ObjectStorageService, bucket_name: str) -> None:
        if not bucket_name:
            raise ValueError("GCS_BUCKET_NAME is required when STORAGE_BACKEND=gcs")
        self.object_storage = object_storage
        self.bucket_name = bucket_name

    @classmethod
    def from_settings(cls) -> "GcsDocumentStorageService":
        settings = get_settings()
        if not settings.gcs_bucket_name:
            raise ValueError("GCS_BUCKET_NAME is required when STORAGE_BACKEND=gcs")
        return cls(get_object_storage_service(), settings.gcs_bucket_name)

    def save(
        self,
        *,
        content: bytes,
        original_filename: str,
        content_type: str,
        document_type: DocumentType,
        owner_user_id: str | None = None,
        organization_id: str | None = None,
        created_by: str | None = None,
    ) -> DocumentRecord:
        document_id = str(uuid.uuid4())
        safe_filename = safe_storage_filename(original_filename)
        object_key = make_safe_object_key("documents", document_id, safe_filename)
        owner = owner_user_id or DEMO_USER_ID
        org = organization_id or DEMO_ORGANIZATION_ID
        self.object_storage.save_object(
            object_key,
            content,
            {
                "content_type": content_type,
                "document_id": document_id,
                "document_type": document_type.value,
                "owner_user_id": owner,
                "organization_id": org,
            },
        )
        record = DocumentRecord(
            document_id=document_id,
            document_type=document_type,
            original_filename=safe_filename,
            safe_filename=safe_filename,
            content_type=content_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            storage_path=f"gcs://{self.bucket_name}/{object_key}",
            owner_user_id=owner,
            organization_id=org,
            created_by=created_by or owner,
        )
        DOCUMENT_CACHE[document_id] = record
        _save_document_record(record)
        return record

    def get(self, document_id: str) -> DocumentRecord:
        try:
            uuid.UUID(document_id)
        except ValueError as exc:
            raise FileNotFoundError("Document not found") from exc
        cached = DOCUMENT_CACHE.get(document_id)
        if cached is not None:
            return cached
        payload = get_json_record("documents", document_id)
        if payload is None:
            raise FileNotFoundError("Document not found")
        record = DocumentRecord.model_validate(payload)
        DOCUMENT_CACHE[record.document_id] = record
        return record

    def update(self, record: DocumentRecord) -> DocumentRecord:
        record = record.model_copy(update={"updated_at": datetime.now(UTC)})
        DOCUMENT_CACHE[record.document_id] = record
        _save_document_record(record)
        return record

    def read_bytes(self, document_id: str) -> bytes:
        record = self.get(document_id)
        return self.object_storage.get_object(_object_key_from_storage_path(record.storage_path, self.bucket_name))


def get_document_storage_service() -> DocumentStorageService:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorageService(settings.document_storage_dir)
    if settings.storage_backend == "gcs":
        return GcsDocumentStorageService.from_settings()
    raise ValueError("Invalid STORAGE_BACKEND")


def _save_document_record(record: DocumentRecord) -> None:
    save_json_record(
        "documents",
        record.document_id,
        record.model_dump(mode="json"),
        record.created_at.isoformat(),
        record.updated_at.isoformat(),
    )


def _object_key_from_storage_path(storage_path: str, bucket_name: str) -> str:
    prefix = f"gcs://{bucket_name}/"
    if not storage_path.startswith(prefix):
        raise FileNotFoundError("Document not found")
    return storage_path.removeprefix(prefix)

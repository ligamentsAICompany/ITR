"""Object storage abstraction for local artifacts and GCS production storage."""

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Response

from app.core.config import get_settings

PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AADHAAR_RE = re.compile(r"\b[0-9]{12}\b")
PAN_TOKEN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
AADHAAR_TOKEN_RE = re.compile(r"[0-9]{12}")


class ObjectStorageService:
    def save_object(self, key: str, content: bytes, metadata: dict[str, Any] | None = None) -> None:
        raise NotImplementedError

    def get_object(self, key: str) -> bytes:
        raise NotImplementedError

    def delete_object(self, key: str) -> None:
        raise NotImplementedError

    def get_metadata(self, key: str) -> dict[str, Any]:
        raise NotImplementedError

    def generate_download_response(self, key: str, *, filename: str, mime_type: str) -> Response:
        return Response(
            content=self.get_object(key),
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


class LocalObjectStorageService(ObjectStorageService):
    def __init__(self, base_dir: str | Path = ".local_objects") -> None:
        self.base_dir = Path(base_dir).resolve()

    def save_object(self, key: str, content: bytes, metadata: dict[str, Any] | None = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        if metadata is not None:
            path.with_suffix(path.suffix + ".metadata.json").write_text(
                json.dumps(_safe_metadata(metadata), sort_keys=True),
                encoding="utf-8",
            )

    def get_object(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete_object(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def get_metadata(self, key: str) -> dict[str, Any]:
        metadata_path = self._path(key).with_suffix(self._path(key).suffix + ".metadata.json")
        if not metadata_path.exists():
            return {}
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    def _path(self, key: str) -> Path:
        path = (self.base_dir / key).resolve()
        if not path.is_relative_to(self.base_dir):
            raise FileNotFoundError("Object not found")
        return path


class GcsObjectStorageService(ObjectStorageService):
    def __init__(self, bucket_name: str | None, client: Any | None = None) -> None:
        if not bucket_name:
            raise ValueError("GCS_BUCKET_NAME is required when STORAGE_BACKEND=gcs")
        self.bucket_name = bucket_name
        self.client = client or self._default_client()
        self.bucket = self.client.bucket(bucket_name)

    def save_object(self, key: str, content: bytes, metadata: dict[str, Any] | None = None) -> None:
        blob = self.bucket.blob(_validate_object_key(key))
        safe_metadata = _safe_metadata(metadata or {})
        blob.metadata = {key: str(value) for key, value in safe_metadata.items()}
        blob.upload_from_string(content, content_type=safe_metadata.get("content_type"))

    def get_object(self, key: str) -> bytes:
        return self.bucket.blob(_validate_object_key(key)).download_as_bytes()

    def delete_object(self, key: str) -> None:
        self.bucket.blob(_validate_object_key(key)).delete()

    def get_metadata(self, key: str) -> dict[str, Any]:
        blob = self.bucket.blob(_validate_object_key(key))
        blob.reload()
        return dict(blob.metadata or {})

    def _default_client(self) -> Any:
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is required when STORAGE_BACKEND=gcs") from exc
        return storage.Client()


def get_object_storage_service() -> ObjectStorageService:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalObjectStorageService()
    if settings.storage_backend == "gcs":
        return GcsObjectStorageService(settings.gcs_bucket_name)
    raise ValueError("Invalid STORAGE_BACKEND")


def make_safe_object_key(prefix: str, *parts: str) -> str:
    safe_prefix = _safe_component(prefix) or "objects"
    safe_parts = [_safe_component(part) for part in parts if _safe_component(part)]
    if not safe_parts:
        safe_parts = [str(uuid4())]
    return "/".join([safe_prefix, *safe_parts])


def safe_storage_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "document"
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    candidate = f"{safe_stem or 'document'}{suffix}"
    if _contains_sensitive_identifier(candidate):
        return f"document{suffix}"
    return candidate


def _validate_object_key(key: str) -> str:
    if key.startswith("/") or ".." in key.split("/"):
        raise ValueError("Unsafe object key")
    if _contains_sensitive_identifier(key):
        raise ValueError("Object key cannot contain PAN or Aadhaar")
    return key


def _safe_component(value: str) -> str:
    candidate = safe_storage_filename(str(value))
    return re.sub(r"[^A-Za-z0-9._/-]+", "_", candidate).strip("._-/")


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if key not in {"storage_path", "raw_text", "raw_document_text", "object_key"}
    }


def _contains_sensitive_identifier(value: str) -> bool:
    return bool(
        PAN_RE.search(value)
        or AADHAAR_RE.search(value)
        or PAN_TOKEN_RE.search(value.upper())
        or AADHAAR_TOKEN_RE.search(value)
    )

"""Object storage abstraction for local artifacts and future GCS storage."""

from pathlib import Path
from typing import Any

from fastapi import Response

from app.core.config import get_settings


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
            path.with_suffix(path.suffix + ".metadata.json").write_text(str(metadata), encoding="utf-8")

    def get_object(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete_object(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def get_metadata(self, key: str) -> dict[str, Any]:
        return {"key": key}

    def _path(self, key: str) -> Path:
        path = (self.base_dir / key).resolve()
        if not path.is_relative_to(self.base_dir):
            raise FileNotFoundError("Object not found")
        return path


class GcsObjectStorageService(ObjectStorageService):
    def __init__(self, bucket_name: str | None) -> None:
        if not bucket_name:
            raise ValueError("GCS_BUCKET_NAME is required when STORAGE_BACKEND=gcs")
        self.bucket_name = bucket_name

    def save_object(self, key: str, content: bytes, metadata: dict[str, Any] | None = None) -> None:
        raise NotImplementedError("GCS object storage requires a production implementation before client use")

    def get_object(self, key: str) -> bytes:
        raise NotImplementedError("GCS object storage requires a production implementation before client use")

    def delete_object(self, key: str) -> None:
        raise NotImplementedError("GCS object storage requires a production implementation before client use")

    def get_metadata(self, key: str) -> dict[str, Any]:
        raise NotImplementedError("GCS object storage requires a production implementation before client use")


def get_object_storage_service() -> ObjectStorageService:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalObjectStorageService()
    if settings.storage_backend == "gcs":
        return GcsObjectStorageService(settings.gcs_bucket_name)
    raise ValueError("Invalid STORAGE_BACKEND")

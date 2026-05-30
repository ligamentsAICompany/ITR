"""Environment-backed runtime configuration."""

from functools import lru_cache
from os import getenv


class Settings:
    api_base_url: str
    debug: bool
    environment: str
    rate_limit_per_minute: int
    max_request_bytes: int
    document_storage_dir: str
    max_upload_bytes: int
    database_url: str | None
    persistence_backend: str
    persistence_storage_dir: str
    demo_auth_enabled: bool
    storage_backend: str
    gcs_bucket_name: str | None
    audit_strict: bool
    cors_allowed_origins: list[str]

    def __init__(self) -> None:
        self.api_base_url = getenv("API_BASE_URL", "http://127.0.0.1:8000")
        self.debug = getenv("DEBUG", "false").lower() in {"1", "true", "yes", "on"}
        self.environment = getenv("ENVIRONMENT", "development")
        self.rate_limit_per_minute = int(getenv("RATE_LIMIT_PER_MINUTE", "120"))
        self.max_request_bytes = int(getenv("MAX_REQUEST_BYTES", "1048576"))
        self.document_storage_dir = getenv("DOCUMENT_STORAGE_DIR", ".local_uploads")
        self.max_upload_bytes = int(getenv("MAX_UPLOAD_BYTES", "10485760"))
        self.database_url = getenv("DATABASE_URL") or None
        self.persistence_backend = getenv("PERSISTENCE_BACKEND", "sqlite").lower()
        self.persistence_storage_dir = getenv("PERSISTENCE_STORAGE_DIR", ".local_persistence")
        self.demo_auth_enabled = getenv("DEMO_AUTH_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        self.storage_backend = getenv("STORAGE_BACKEND", "local").lower()
        self.gcs_bucket_name = getenv("GCS_BUCKET_NAME") or None
        self.audit_strict = getenv("AUDIT_STRICT", "false").lower() in {"1", "true", "yes", "on"}
        self.cors_allowed_origins = _csv(
            getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]

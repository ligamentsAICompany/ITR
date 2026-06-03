"""Environment-backed runtime configuration."""

from functools import lru_cache
from os import getenv
from urllib.parse import urlparse


class Settings:
    api_base_url: str
    debug: bool
    environment: str
    auth_mode: str
    allow_demo_auth_in_production: bool
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
    jwt_issuer: str | None
    jwt_audience: str | None
    jwt_secret: str | None
    jwt_jwks_url: str | None
    google_oauth_client_id: str | None
    audit_strict: bool
    cors_allowed_origins: list[str]
    next_public_api_base_url: str | None
    filing_provider: str
    filing_provider_mode: str
    secret_backend: str
    gcp_project_id: str | None
    allow_sandbox_provider_calls: bool
    allow_live_filing: bool
    live_filing_approval_ticket: str | None
    live_filing_approved_by: str | None
    live_filing_approved_at: str | None
    eri_client_id: str | None
    eri_client_secret: str | None
    eri_client_id_secret_name: str | None
    eri_client_secret_secret_name: str | None
    eri_private_key_secret_name: str | None
    eri_cert_secret_name: str | None
    eri_sandbox_client_id_secret_name: str | None
    eri_sandbox_client_secret_secret_name: str | None
    eri_sandbox_private_key_secret_name: str | None
    eri_sandbox_cert_secret_name: str | None
    eri_base_url: str | None
    eri_token_url: str | None
    eri_callback_url: str | None
    eri_cert_path: str | None
    eri_timeout_seconds: int
    eri_retry_count: int
    eri_retry_backoff_seconds: float
    eri_status_poll_interval_seconds: int
    allow_unsigned_provider_callbacks: bool
    store_provider_raw_payloads: bool
    provider_raw_payload_retention_days: int
    mock_filing_outcome: str
    auto_load_demo_schema_packs: bool

    def __init__(self) -> None:
        self.api_base_url = getenv("API_BASE_URL", "http://127.0.0.1:8000")
        self.debug = getenv("DEBUG", "false").lower() in {"1", "true", "yes", "on"}
        self.environment = getenv("ENVIRONMENT", "demo").lower()
        self.auth_mode = getenv("AUTH_MODE", "demo").lower()
        self.allow_demo_auth_in_production = getenv("ALLOW_DEMO_AUTH_IN_PRODUCTION", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.rate_limit_per_minute = int(getenv("RATE_LIMIT_PER_MINUTE", "120"))
        self.max_request_bytes = int(getenv("MAX_REQUEST_BYTES", "1048576"))
        self.document_storage_dir = getenv(
            "DOCUMENT_STORAGE_DIR",
            "/tmp/itr_demo_uploads" if self.environment == "demo" else ".local_uploads",
        )
        self.max_upload_bytes = int(getenv("MAX_UPLOAD_BYTES", "10485760"))
        self.persistence_backend = getenv("PERSISTENCE_BACKEND", "sqlite").lower()
        self.database_url = _default_database_url(self.persistence_backend)
        self.persistence_storage_dir = getenv("PERSISTENCE_STORAGE_DIR", ".local_persistence")
        self.demo_auth_enabled = getenv("DEMO_AUTH_ENABLED", "true" if self.environment == "demo" else "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.storage_backend = getenv("STORAGE_BACKEND", "local").lower()
        self.gcs_bucket_name = getenv("GCS_BUCKET_NAME") or None
        self.jwt_issuer = getenv("JWT_ISSUER") or None
        self.jwt_audience = getenv("JWT_AUDIENCE") or None
        self.jwt_secret = getenv("JWT_SECRET") or None
        self.jwt_jwks_url = getenv("JWT_JWKS_URL") or None
        self.google_oauth_client_id = getenv("GOOGLE_OAUTH_CLIENT_ID") or None
        self.audit_strict = getenv("AUDIT_STRICT", "false").lower() in {"1", "true", "yes", "on"}
        self.cors_allowed_origins = _csv(
            getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        )
        self.next_public_api_base_url = getenv("NEXT_PUBLIC_API_BASE_URL") or None
        self.filing_provider = getenv("FILING_PROVIDER", "mock").lower()
        provider_default_mode = {"eri_sandbox": "sandbox", "eri_live": "live"}.get(self.filing_provider, self.filing_provider)
        self.filing_provider_mode = getenv("FILING_PROVIDER_MODE", provider_default_mode).lower()
        self.secret_backend = getenv("SECRET_BACKEND", "env").lower()
        self.gcp_project_id = getenv("GCP_PROJECT_ID") or None
        self.allow_sandbox_provider_calls = getenv("ALLOW_SANDBOX_PROVIDER_CALLS", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.allow_live_filing = getenv("ALLOW_LIVE_FILING", "false").lower() in {"1", "true", "yes", "on"}
        self.live_filing_approval_ticket = getenv("LIVE_FILING_APPROVAL_TICKET") or None
        self.live_filing_approved_by = getenv("LIVE_FILING_APPROVED_BY") or None
        self.live_filing_approved_at = getenv("LIVE_FILING_APPROVED_AT") or None
        self.eri_client_id = getenv("ERI_CLIENT_ID") or None
        self.eri_client_secret = getenv("ERI_CLIENT_SECRET") or None
        self.eri_client_id_secret_name = getenv("ERI_CLIENT_ID_SECRET_NAME") or None
        self.eri_client_secret_secret_name = getenv("ERI_CLIENT_SECRET_SECRET_NAME") or None
        self.eri_private_key_secret_name = getenv("ERI_PRIVATE_KEY_SECRET_NAME") or None
        self.eri_cert_secret_name = getenv("ERI_CERT_SECRET_NAME") or None
        self.eri_sandbox_client_id_secret_name = getenv("ERI_SANDBOX_CLIENT_ID_SECRET_NAME") or None
        self.eri_sandbox_client_secret_secret_name = getenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME") or None
        self.eri_sandbox_private_key_secret_name = getenv("ERI_SANDBOX_PRIVATE_KEY_SECRET_NAME") or None
        self.eri_sandbox_cert_secret_name = getenv("ERI_SANDBOX_CERT_SECRET_NAME") or None
        self.eri_base_url = getenv("ERI_BASE_URL") or None
        self.eri_token_url = getenv("ERI_TOKEN_URL") or None
        self.eri_callback_url = getenv("ERI_CALLBACK_URL") or None
        self.eri_cert_path = getenv("ERI_CERT_PATH") or None
        self.eri_timeout_seconds = int(getenv("ERI_TIMEOUT_SECONDS", "10"))
        self.eri_retry_count = int(getenv("ERI_RETRY_COUNT", "2"))
        self.eri_retry_backoff_seconds = float(getenv("ERI_RETRY_BACKOFF_SECONDS", "1"))
        self.eri_status_poll_interval_seconds = int(getenv("ERI_STATUS_POLL_INTERVAL_SECONDS", "30"))
        self.allow_unsigned_provider_callbacks = getenv("ALLOW_UNSIGNED_PROVIDER_CALLBACKS", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.store_provider_raw_payloads = getenv("STORE_PROVIDER_RAW_PAYLOADS", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.provider_raw_payload_retention_days = int(getenv("PROVIDER_RAW_PAYLOAD_RETENTION_DAYS", "30"))
        self.mock_filing_outcome = getenv("MOCK_FILING_OUTCOME", "success").lower()
        auto_load_default = "true" if self.environment == "demo" else "false"
        self.auto_load_demo_schema_packs = getenv("AUTO_LOAD_DEMO_SCHEMA_PACKS", auto_load_default).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def live_filing_approval_complete(self) -> bool:
        return bool(self.live_filing_approval_ticket and self.live_filing_approved_by and self.live_filing_approved_at)

    def validate_startup(self) -> None:
        errors: list[str] = []
        if self.environment not in {"demo", "development", "test", "production"}:
            errors.append("ENVIRONMENT must be demo, development, test, or production")
        if self.auth_mode not in {"demo", "jwt", "google"}:
            errors.append("AUTH_MODE must be demo, jwt, or google")
        if self.persistence_backend not in {"memory", "sqlite", "postgres"}:
            errors.append("PERSISTENCE_BACKEND must be memory, sqlite, or postgres")
        if self.storage_backend not in {"local", "gcs"}:
            errors.append("STORAGE_BACKEND must be local or gcs")
        if self.filing_provider not in {"mock", "sandbox", "live", "eri_sandbox", "eri_live"}:
            errors.append("FILING_PROVIDER must be mock, eri_sandbox, or eri_live")
        if self.filing_provider_mode not in {"mock", "sandbox", "live"}:
            errors.append("FILING_PROVIDER_MODE must be mock, sandbox, or live")
        if self.secret_backend not in {"env", "gcp_secret_manager"}:
            errors.append("SECRET_BACKEND must be env or gcp_secret_manager")
        if self.mock_filing_outcome not in {"success", "failure", "pending"}:
            errors.append("MOCK_FILING_OUTCOME must be success, failure, or pending")
        if self.allow_live_filing and not self.live_filing_approval_complete:
            errors.append("LIVE_FILING_APPROVAL_TICKET, LIVE_FILING_APPROVED_BY, and LIVE_FILING_APPROVED_AT are required when ALLOW_LIVE_FILING=true")
        if self.persistence_backend == "postgres" and not self.database_url:
            errors.append("DATABASE_URL is required when PERSISTENCE_BACKEND=postgres")
        if self.storage_backend == "gcs" and not self.gcs_bucket_name:
            errors.append("GCS_BUCKET_NAME is required when STORAGE_BACKEND=gcs")
        if self.auth_mode == "jwt" and not (self.jwt_secret or self.jwt_jwks_url):
            errors.append("JWT_SECRET or JWT_JWKS_URL is required when AUTH_MODE=jwt")
        if self.auth_mode == "jwt" and not (self.jwt_issuer and self.jwt_audience):
            errors.append("JWT_ISSUER and JWT_AUDIENCE are required when AUTH_MODE=jwt")
        if self.auth_mode == "google" and not self.google_oauth_client_id:
            errors.append("GOOGLE_OAUTH_CLIENT_ID is required when AUTH_MODE=google")
        if self.rate_limit_per_minute <= 0:
            errors.append("RATE_LIMIT_PER_MINUTE must be positive")
        if self.max_request_bytes <= 0:
            errors.append("MAX_REQUEST_BYTES must be positive")
        if self.max_upload_bytes <= 0:
            errors.append("MAX_UPLOAD_BYTES must be positive")
        if self.eri_timeout_seconds <= 0:
            errors.append("ERI_TIMEOUT_SECONDS must be positive")
        if self.eri_retry_count < 0:
            errors.append("ERI_RETRY_COUNT cannot be negative")
        if self.eri_retry_backoff_seconds < 0:
            errors.append("ERI_RETRY_BACKOFF_SECONDS cannot be negative")
        if self.eri_status_poll_interval_seconds <= 0:
            errors.append("ERI_STATUS_POLL_INTERVAL_SECONDS must be positive")
        if self.provider_raw_payload_retention_days <= 0:
            errors.append("PROVIDER_RAW_PAYLOAD_RETENTION_DAYS must be positive")
        if self.is_production:
            if self.debug:
                errors.append("DEBUG=false is required in production")
            if "*" in self.cors_allowed_origins:
                errors.append("CORS_ALLOWED_ORIGINS cannot include * in production")
            if self.auth_mode == "demo" and not self.allow_demo_auth_in_production:
                errors.append("ALLOW_DEMO_AUTH_IN_PRODUCTION=true is required for production demo auth")
            for name, value in (
                ("API_BASE_URL", self.api_base_url),
                ("NEXT_PUBLIC_API_BASE_URL", self.next_public_api_base_url or ""),
            ):
                if _is_localhost_url(value):
                    errors.append(f"{name} cannot use localhost in production")
        if errors:
            raise ValueError("; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _default_database_url(persistence_backend: str) -> str | None:
    configured = getenv("DATABASE_URL")
    if configured:
        return configured
    if persistence_backend == "sqlite":
        return "sqlite:////tmp/itr_demo.db"
    return None


def _is_localhost_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    host = parsed.hostname or ""
    return host in {"localhost", "127.0.0.1", "::1"}

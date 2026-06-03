import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from app.core.config import Settings, get_settings
from app.main import app
from app.services.provider_diagnostics_service import ProviderDiagnosticsService


DEMO_ENV_VARS = (
    "ENVIRONMENT",
    "AUTH_MODE",
    "DEMO_AUTH_ENABLED",
    "ALLOW_DEMO_AUTH_IN_PRODUCTION",
    "PERSISTENCE_BACKEND",
    "DATABASE_URL",
    "STORAGE_BACKEND",
    "FILING_PROVIDER",
    "FILING_PROVIDER_MODE",
    "ALLOW_LIVE_FILING",
    "ALLOW_SANDBOX_PROVIDER_CALLS",
    "DEBUG",
    "SECRET_BACKEND",
    "GCP_PROJECT_ID",
    "GCS_BUCKET_NAME",
    "JWT_ISSUER",
    "JWT_AUDIENCE",
    "JWT_SECRET",
    "JWT_JWKS_URL",
    "GOOGLE_OAUTH_CLIENT_ID",
    "AUTO_LOAD_DEMO_SCHEMA_PACKS",
    "DOCUMENT_STORAGE_DIR",
)


def clear_demo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in DEMO_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()


def test_default_config_boots_safe_demo_mode_without_env(monkeypatch):
    clear_demo_env(monkeypatch)

    settings = Settings()
    settings.validate_startup()

    assert settings.environment == "demo"
    assert settings.auth_mode == "demo"
    assert settings.demo_auth_enabled is True
    assert settings.persistence_backend == "sqlite"
    assert settings.database_url == "sqlite:////tmp/itr_demo.db"
    assert settings.storage_backend == "local"
    assert settings.document_storage_dir == "/tmp/itr_demo_uploads"
    assert settings.filing_provider == "mock"
    assert settings.filing_provider_mode == "mock"
    assert settings.allow_live_filing is False
    assert settings.allow_sandbox_provider_calls is False
    assert settings.debug is False
    assert settings.auto_load_demo_schema_packs is True


def test_production_blocks_unsafe_demo_auth_unless_explicitly_allowed(monkeypatch):
    clear_demo_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "https://app.example.com")

    settings = Settings()

    with pytest.raises(ValueError, match="ALLOW_DEMO_AUTH_IN_PRODUCTION"):
        settings.validate_startup()


def test_production_blocks_debug_true(monkeypatch):
    clear_demo_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("JWT_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("JWT_AUDIENCE", "itr-api")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "https://app.example.com")

    with pytest.raises(ValueError, match="DEBUG=false"):
        Settings().validate_startup()


def test_production_blocks_wildcard_cors(monkeypatch):
    clear_demo_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("JWT_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("JWT_AUDIENCE", "itr-api")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "https://app.example.com")

    with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS"):
        Settings().validate_startup()


def test_production_blocks_live_filing_without_approval_metadata(monkeypatch):
    clear_demo_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("JWT_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("JWT_AUDIENCE", "itr-api")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("ALLOW_LIVE_FILING", "true")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "https://app.example.com")

    with pytest.raises(ValueError, match="LIVE_FILING_APPROVAL_TICKET"):
        Settings().validate_startup()


def test_demo_health_exposes_safe_default_fields_without_secret_env(monkeypatch):
    clear_demo_env(monkeypatch)
    client = TestClient(app)

    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "api_version": "v1",
        "environment": "demo",
        "auth_mode": "demo",
        "persistence_backend": "sqlite",
        "storage_backend": "local",
        "provider_mode": "mock",
        "live_filing_enabled": False,
    }
    assert "GCP_PROJECT_ID" not in response.text
    assert "GCS_BUCKET_NAME" not in response.text
    assert "JWT_SECRET" not in response.text
    assert "DOCUMENT_STORAGE_DIR" not in response.text
    assert "/tmp" not in response.text


def test_production_defaults_do_not_auto_load_demo_schema_packs(monkeypatch):
    clear_demo_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("JWT_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("JWT_AUDIENCE", "itr-api")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "https://app.example.com")

    settings = Settings()

    assert settings.auto_load_demo_schema_packs is False


def test_demo_health_and_diagnostics_routes_return_200_before_manual_setup(monkeypatch):
    clear_demo_env(monkeypatch)
    client = TestClient(app)

    health = client.get("/v1/health")
    diagnostics = client.get("/v1/filing/provider-diagnostics")

    assert health.status_code == 200, health.text
    assert diagnostics.status_code == 200, diagnostics.text
    assert diagnostics.json()["mode"] == "mock"
    assert diagnostics.json()["live_filing_enabled"] is False


def test_normalize_valid_synthetic_payload_works_under_demo_defaults(monkeypatch):
    clear_demo_env(monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/v1/normalize",
        json={
            "pan": "ABCDE1234F",
            "aadhaar": "123456789012",
            "entity_type": "individual",
            "residency_status": "resident",
            "salary_income": 1000000,
            "previous_year": "2025-26",
            "assessment_year": "2026-27",
            "return_filing_reason": "mandatory",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user_identity"]["pan"] == "ABCDE1234F"
    assert payload["user_identity"]["aadhaar_number"] == "123456789012"
    assert payload["income_heads"]["salary"]["gross_amount"] == 1000000


def test_provider_diagnostics_default_to_mock_with_live_and_sandbox_disabled(monkeypatch):
    clear_demo_env(monkeypatch)

    diagnostics = ProviderDiagnosticsService().current()

    assert diagnostics.provider == "mock"
    assert diagnostics.mode == "mock"
    assert diagnostics.configured is True
    assert diagnostics.live_filing_enabled is False
    assert diagnostics.live_enabled is False
    assert diagnostics.sandbox_calls_allowed is False
    assert diagnostics.secret_backend == "env"


def test_demo_defaults_do_not_require_gcp_secret_manager_gcs_or_jwt(monkeypatch):
    clear_demo_env(monkeypatch)

    settings = Settings()
    settings.validate_startup()

    assert settings.secret_backend == "env"
    assert settings.gcp_project_id is None
    assert settings.gcs_bucket_name is None
    assert settings.jwt_secret is None
    assert settings.jwt_jwks_url is None


def test_cloud_run_image_includes_demo_schema_packs():
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert "COPY demo_data ./demo_data" in content

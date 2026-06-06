import types
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core import database
from app.core.database import get_json_record, persistence_backend, save_json_record
from app.main import app
from app.models.auth import SessionContext, UserRole
from app.models.document import DocumentType
from app.services.authorization_service import AuthorizationService
from app.services.object_storage_service import GcsObjectStorageService, make_safe_object_key
from app.services.storage_service import GcsDocumentStorageService


client = TestClient(app)


USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def auth(user_id=USER_A, role="taxpayer", org_id=ORG_A):
    return {
        "X-Demo-User-Id": user_id,
        "X-Demo-User-Role": role,
        "X-Demo-Organization-Id": org_id,
    }


def test_postgres_backend_requires_database_url(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "postgres")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="DATABASE_URL is required"):
            persistence_backend()
    finally:
        get_settings.cache_clear()


def test_postgres_json_persistence_uses_stable_crud_interface(monkeypatch):
    stored = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params=None):
            if query.lstrip().upper().startswith("INSERT"):
                stored[params[0]] = params[1]
            elif query.lstrip().upper().startswith("SELECT"):
                self.row = (stored.get(params[0]),)

        def fetchone(self):
            return getattr(self, "row", None)

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return FakeCursor()

    @contextmanager
    def fake_postgres_connection():
        yield FakeConnection()

    monkeypatch.setenv("PERSISTENCE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/itr")
    monkeypatch.setattr(database, "postgres_connection", fake_postgres_connection)
    get_settings.cache_clear()
    try:
        save_json_record(
            "validation_reports",
            "run-1",
            {"validation_run_id": "run-1", "owner_user_id": USER_A, "organization_id": ORG_A},
            "2026-05-30T00:00:00+00:00",
            "2026-05-30T00:00:00+00:00",
        )
        payload = get_json_record("validation_reports", "run-1")
    finally:
        get_settings.cache_clear()

    assert payload["validation_run_id"] == "run-1"
    assert payload["owner_user_id"] == USER_A


def test_gcs_backend_requires_bucket(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "gcs")
    monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="GCS_BUCKET_NAME is required"):
            GcsDocumentStorageService.from_settings()
    finally:
        get_settings.cache_clear()


def test_gcs_object_storage_uses_safe_keys_and_client_methods():
    class FakeBlob:
        def __init__(self):
            self.content = b""
            self.metadata = {}
            self.content_type = None
            self.deleted = False

        def upload_from_string(self, content, content_type=None):
            self.content = content
            self.content_type = content_type

        def download_as_bytes(self):
            return self.content

        def reload(self):
            return None

        def delete(self):
            self.deleted = True

    class FakeBucket:
        def __init__(self):
            self.blobs = {}

        def blob(self, key):
            self.blobs.setdefault(key, FakeBlob())
            return self.blobs[key]

    class FakeClient:
        def __init__(self):
            self.bucket_obj = FakeBucket()

        def bucket(self, _name):
            return self.bucket_obj

    client_stub = FakeClient()
    storage = GcsObjectStorageService("itr-bucket", client=client_stub)
    key = make_safe_object_key("documents", "ABCDE1234F.pdf")

    storage.save_object(key, b"payload", {"content_type": "application/pdf", "owner_user_id": USER_A})

    assert "ABCDE1234F" not in key
    assert storage.get_object(key) == b"payload"
    assert storage.get_metadata(key)["owner_user_id"] == USER_A
    storage.delete_object(key)
    assert client_stub.bucket_obj.blobs[key].deleted is True


def test_production_config_rejects_unsafe_values(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.delenv("ALLOW_DEMO_AUTH_IN_PRODUCTION", raising=False)
    get_settings.cache_clear()
    try:
        settings = Settings()
        with pytest.raises(ValueError) as exc:
            settings.validate_startup()
    finally:
        get_settings.cache_clear()

    message = str(exc.value)
    assert "DEBUG=false" in message
    assert "CORS_ALLOWED_ORIGINS" in message
    assert "ALLOW_DEMO_AUTH_IN_PRODUCTION" in message


def test_jwt_auth_rejects_missing_config(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_JWKS_URL", raising=False)
    get_settings.cache_clear()
    try:
        response = client.post(
            "/v1/uploads",
            data={"document_type": "form16"},
            files={"file": ("form16.csv", b"Gross Salary\n1200000\n", "text/csv")},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 401


def test_jwt_auth_accepts_valid_test_token(monkeypatch, tmp_path):
    jwt = pytest.importorskip("jwt")
    secret = "test-secret-with-at-least-32-bytes"
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("JWT_SECRET", secret)
    monkeypatch.setenv("JWT_ISSUER", "itr-tests")
    monkeypatch.setenv("JWT_AUDIENCE", "itr-api")
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    token = jwt.encode(
        {
            "sub": USER_A,
            "email": "taxpayer@example.test",
            "role": "reviewer",
            "organization_id": ORG_A,
            "iss": "itr-tests",
            "aud": "itr-api",
        },
        secret,
        algorithm="HS256",
    )
    try:
        response = client.post(
            "/v1/uploads",
            data={"document_type": "form16"},
            files={"file": ("form16.csv", b"Gross Salary\n1200000\n", "text/csv")},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200, response.text
    assert "owner_user_id" not in response.text


def test_jwt_auth_rejects_invalid_token(monkeypatch):
    secret = "test-secret-with-at-least-32-bytes"
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("JWT_SECRET", secret)
    monkeypatch.setenv("JWT_ISSUER", "itr-tests")
    monkeypatch.setenv("JWT_AUDIENCE", "itr-api")
    get_settings.cache_clear()
    try:
        response = client.get("/v1/health", headers={"Authorization": "Bearer not-a-token"})
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    protected = client.post(
        "/v1/uploads",
        data={"document_type": "form16"},
        files={"file": ("form16.csv", b"Gross Salary\n1200000\n", "text/csv")},
        headers={"Authorization": "Bearer not-a-token"},
    )
    assert protected.status_code == 401


def test_service_role_cannot_read_arbitrary_taxpayer_resource():
    session = SessionContext(
        session_id="99999999-9999-4999-8999-999999999999",
        user_id="00000000-0000-4000-8000-000000000999",
        organization_id=ORG_A,
        role=UserRole.SERVICE,
        request_id="88888888-8888-4888-8888-888888888888",
    )
    resource = types.SimpleNamespace(owner_user_id=USER_A, organization_id=ORG_A, created_by=USER_A)

    decision = AuthorizationService().can_read_document(session, resource)

    assert decision.allowed is False
    assert decision.reason == "service_not_authorized"


def test_health_endpoint_exposes_safe_readiness_fields(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    get_settings.cache_clear()
    try:
        response = client.get("/v1/health")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["api_version"] == "v1"
    assert payload["persistence_backend"] == "sqlite"
    assert payload["storage_backend"] == "local"
    assert payload["auth_mode"] == "demo"
    assert "DATABASE_URL" not in response.text
    assert "GCS_BUCKET_NAME" not in response.text
    assert "JWT_SECRET" not in response.text


def test_gcs_document_storage_persists_metadata_without_internal_key(monkeypatch):
    class MemoryObjects:
        def __init__(self):
            self.objects = {}

        def save_object(self, key, content, metadata=None):
            self.objects[key] = (content, metadata or {})

        def get_object(self, key):
            return self.objects[key][0]

        def delete_object(self, key):
            self.objects.pop(key, None)

        def get_metadata(self, key):
            return self.objects[key][1]

    monkeypatch.setenv("PERSISTENCE_BACKEND", "memory")
    get_settings.cache_clear()
    storage = GcsDocumentStorageService(object_storage=MemoryObjects(), bucket_name="itr-bucket")

    record = storage.save(
        content=b"Gross Salary\n1200000\n",
        original_filename="ABCDE1234F.pdf",
        content_type="application/pdf",
        document_type=DocumentType.PDF_TEXT,
        owner_user_id=USER_A,
        organization_id=ORG_A,
        created_by=USER_A,
    )

    assert "ABCDE1234F" not in record.safe_filename
    assert "ABCDE1234F" not in record.storage_path
    assert storage.read_bytes(record.document_id) == b"Gross Salary\n1200000\n"
    assert "storage_path" not in record.to_public_metadata().model_dump_json()

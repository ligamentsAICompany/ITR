import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.main import app
from app.models.filing_package import FilingPackage, FilingPackageStatus
from app.models.filing_submission import FilingSubmission, SubmissionStatus
from app.models.itr_export import ItrExport, ItrExportStatus, OfficialSchemaValidationResult
from app.models.provider_spec import AuthType, ProviderMode, ProviderSpec, SignatureType
from app.repositories.audit_repository import AUDIT_EVENT_CACHE
from app.repositories.filing_package_repository import FILING_PACKAGE_CACHE
from app.repositories.filing_workflow_repository import FILING_APPROVAL_CACHE, FILING_CONSENT_CACHE, FILING_SUBMISSION_CACHE
from app.repositories.itr_export_repository import ITR_EXPORT_CACHE
from app.repositories.provider_spec_repository import PROVIDER_CONTRACT_RESULT_CACHE, PROVIDER_SPEC_CACHE, ProviderSpecRepository
from app.services.eri_client import EriClient
from app.services.eri_provider import EriProvider
from app.services.provider_contract_test_service import ProviderContractTestService
from app.services.provider_credentials_service import ProviderCredentialsService
from app.services.provider_diagnostics_service import ProviderDiagnosticsService
from app.services.secret_manager_service import SecretManagerService


client = TestClient(app)
USER_A = "11111111-1111-4111-8111-111111111111"
ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def setup_function():
    rate_limiter.clear()
    get_settings.cache_clear()
    PROVIDER_SPEC_CACHE.clear()
    PROVIDER_CONTRACT_RESULT_CACHE.clear()
    FILING_PACKAGE_CACHE.clear()
    ITR_EXPORT_CACHE.clear()
    FILING_CONSENT_CACHE.clear()
    FILING_APPROVAL_CACHE.clear()
    FILING_SUBMISSION_CACHE.clear()
    AUDIT_EVENT_CACHE.clear()
    routes.PROVIDER_CALLBACK_REPLAY_CACHE.clear()


def teardown_function():
    rate_limiter.clear()
    get_settings.cache_clear()
    routes.PROVIDER_CALLBACK_REPLAY_CACHE.clear()


def auth():
    return {
        "X-Demo-User-Id": USER_A,
        "X-Demo-User-Role": "admin",
        "X-Demo-Organization-Id": ORG_A,
    }


def sandbox_spec(**updates):
    data = {
        "provider_name": "eri",
        "provider_mode": ProviderMode.SANDBOX,
        "spec_version": "sandbox-v1",
        "base_url": "https://sandbox.invalid",
        "token_url": "https://sandbox.invalid/token",
        "callback_url": "https://api.example.com/v1/filing/provider-callbacks/eri_sandbox",
        "supported_operations": ["submit_return", "status_check", "callback"],
        "auth_type": AuthType.BEARER_TOKEN,
        "signature_type": SignatureType.HMAC_SIGNATURE,
        "payload_format": "json",
        "status_mapping_version": "v1",
        "is_active": True,
    }
    data.update(updates)
    return ProviderSpec(**data)


def save_sandbox_spec(**updates):
    return ProviderSpecRepository().save(sandbox_spec(**updates))


class FakeSandboxTransport:
    def __init__(self, *, fail_operation: str | None = None) -> None:
        self.fail_operation = fail_operation
        self.calls: list[dict] = []

    def __call__(self, *, method: str, url: str, headers: dict[str, str], payload: dict | bytes | None, timeout_seconds: int) -> dict:
        self.calls.append({"method": method, "url": url, "headers": headers, "payload": payload, "timeout_seconds": timeout_seconds})
        if self.fail_operation and self.fail_operation in url:
            raise TimeoutError("sandbox timeout token=secret ABCDE1234F")
        if "token" in url:
            return {"access_token": "sandbox-token", "token_type": "Bearer", "expires_in": 300}
        if "validate" in url:
            return {"status": "validated", "raw_status_code": "SANDBOX_VALID"}
        if "submit" in url:
            return {"status": "submitted", "provider_reference_id": "ERI-SBX-REF-1234", "raw_status_code": "SANDBOX_ACCEPTED"}
        if "status" in url:
            return {"status": "pending_verification", "provider_reference_id": "ERI-SBX-REF-1234", "raw_status_code": "SANDBOX_PENDING"}
        return {"status": "unsupported"}


def test_env_secret_backend_loads_sandbox_credentials_and_never_exposes_values(monkeypatch):
    monkeypatch.setenv("SECRET_BACKEND", "env")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_ID_SECRET_NAME", "SANDBOX_CLIENT_ID_VALUE")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME", "SANDBOX_CLIENT_SECRET_VALUE")
    monkeypatch.setenv("SANDBOX_CLIENT_ID_VALUE", "sandbox-client-id")
    monkeypatch.setenv("SANDBOX_CLIENT_SECRET_VALUE", "sandbox-credential-value")
    get_settings.cache_clear()

    credentials = ProviderCredentialsService().load(mode=ProviderMode.SANDBOX)

    assert credentials.configured is True
    assert credentials.client_id == "sandbox-client-id"
    assert credentials.client_secret == "sandbox-credential-value"
    public = credentials.safe_public_dict()
    assert public["configured"] is True
    assert "sandbox-client" not in json.dumps(public)
    assert "secret" not in json.dumps(public).lower()


def test_gcp_secret_backend_missing_project_fails_safely(monkeypatch):
    monkeypatch.setenv("SECRET_BACKEND", "gcp_secret_manager")
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    get_settings.cache_clear()

    value = SecretManagerService().get_secret("eri-sandbox-client-id")

    assert value.available is False
    assert "project" in (value.safe_error or "").lower()
    assert "eri-sandbox-client-id" not in (value.safe_error or "")


def test_gcp_secret_backend_mocked_fetch_succeeds(monkeypatch):
    class FakeClient:
        def secret_version_path(self, project_id, secret_name, version):
            return f"projects/{project_id}/secrets/{secret_name}/versions/{version}"

        def access_secret_version(self, request):
            assert request["name"] == "projects/test-project/secrets/eri-sandbox-client-secret/versions/latest"

            class Payload:
                data = b"mocked-provider-value"

            class Response:
                payload = Payload()

            return Response()

    monkeypatch.setenv("SECRET_BACKEND", "gcp_secret_manager")
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    get_settings.cache_clear()

    value = SecretManagerService(secret_manager_client=FakeClient()).get_secret("eri-sandbox-client-secret")

    assert value.available is True
    assert value.value == "mocked-provider-value"


def test_sandbox_configured_but_calls_disabled_is_blocked(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    monkeypatch.setenv("SECRET_BACKEND", "env")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_ID_SECRET_NAME", "SBX_ID")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME", "SBX_SECRET")
    monkeypatch.setenv("SBX_ID", "sandbox-client")
    monkeypatch.setenv("SBX_SECRET", "sandbox-credential-value")
    monkeypatch.setenv("ALLOW_SANDBOX_PROVIDER_CALLS", "false")
    get_settings.cache_clear()
    save_sandbox_spec()

    diagnostics = ProviderDiagnosticsService().current()

    assert diagnostics.sandbox_configured is True
    assert diagnostics.sandbox_calls_allowed is False
    assert diagnostics.configured is False
    assert diagnostics.safe_readiness == "blocked"
    assert "sandbox_provider_calls_disabled" in diagnostics.safe_missing_config


def test_sandbox_calls_enabled_but_missing_credentials_is_blocked(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    monkeypatch.setenv("ALLOW_SANDBOX_PROVIDER_CALLS", "true")
    monkeypatch.delenv("ERI_SANDBOX_CLIENT_ID_SECRET_NAME", raising=False)
    monkeypatch.delenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME", raising=False)
    monkeypatch.delenv("ERI_CLIENT_ID", raising=False)
    monkeypatch.delenv("ERI_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    save_sandbox_spec()

    diagnostics = ProviderDiagnosticsService().current()

    assert diagnostics.sandbox_configured is False
    assert diagnostics.configured is False
    assert "ERI_SANDBOX_CLIENT_ID" in diagnostics.safe_missing_config
    assert "ERI_SANDBOX_CLIENT_SECRET" in diagnostics.safe_missing_config


def test_sandbox_transport_submit_status_and_safe_failure_mapping():
    transport = FakeSandboxTransport()
    provider = EriProvider(
        mode=ProviderMode.SANDBOX,
        client=EriClient(
            base_url="https://sandbox.invalid",
            token_url="https://sandbox.invalid/token",
            timeout_seconds=5,
            retry_count=0,
            allow_network=True,
            mode=ProviderMode.SANDBOX,
            transport=transport,
            access_token="sandbox-token",
        ),
        sandbox_mocked=False,
    )

    validation = provider.validate_export_payload(package_id="pkg-1", export_id="exp-1", payload=b'{"test":true}')
    submitted = provider.submit_return(package_id="pkg-1", export_id="exp-1", payload=b'{"test":true}')
    status = provider.get_submission_status(provider_reference_id=submitted.provider_reference_id or "")

    assert validation.success is True
    assert submitted.success is True
    assert submitted.provider_reference_id == "ERI-SBX-REF-1234"
    assert status.normalized_status == SubmissionStatus.PENDING_VERIFICATION
    assert all("sandbox.invalid" in call["url"] for call in transport.calls)

    failing = EriProvider(
        mode=ProviderMode.SANDBOX,
        client=EriClient(
            base_url="https://sandbox.invalid",
            token_url="https://sandbox.invalid/token",
            timeout_seconds=5,
            retry_count=0,
            allow_network=True,
            mode=ProviderMode.SANDBOX,
            transport=FakeSandboxTransport(fail_operation="submit"),
            access_token="sandbox-token",
        ),
        sandbox_mocked=False,
    ).submit_return(package_id="pkg-1", export_id="exp-1", payload=b'{"pan":"ABCDE1234F"}')

    assert failing.success is False
    assert failing.status == "TIMEOUT"
    assert "ABCDE1234F" not in (failing.safe_message or "")
    assert "secret" not in (failing.safe_message or "").lower()


def test_sandbox_contract_not_verified_until_allowed_and_credentials_available(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    monkeypatch.setenv("ALLOW_SANDBOX_PROVIDER_CALLS", "false")
    get_settings.cache_clear()

    result = ProviderContractTestService().run(provider="eri", mode="sandbox")

    assert result.status == "not_verified"
    assert any("ALLOW_SANDBOX_PROVIDER_CALLS" in failure for failure in result.failures)
    latest = ProviderDiagnosticsService().current().last_sandbox_contract_test_at
    assert latest is not None


def test_callback_signature_uses_sandbox_secret_and_rejects_invalid_or_replay(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("ALLOW_DEMO_AUTH_IN_PRODUCTION", "true")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("SECRET_BACKEND", "env")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME", "SBX_CALLBACK_SECRET")
    monkeypatch.setenv("SBX_CALLBACK_SECRET", "sandbox-signing-value")
    get_settings.cache_clear()
    submission = FilingSubmission(
        package_id="pkg-callback",
        export_id="exp-callback",
        provider_reference_id="ERI-SBX-CB-123",
        submission_status=SubmissionStatus.SUBMITTED,
    )
    FILING_SUBMISSION_CACHE[submission.submission_id] = submission
    payload = {"callback_id": "cb-1", "provider_reference_id": "ERI-SBX-CB-123", "provider_status": "acknowledgement_available"}
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = "2026-05-30T00:00:00Z"
    nonce = "sandbox-nonce"
    signature = hmac.new(b"sandbox-signing-value", body + timestamp.encode() + nonce.encode(), hashlib.sha256).hexdigest()

    invalid = client.post(
        "/v1/filing/provider-callbacks/eri_sandbox",
        content=body,
        headers={"Content-Type": "application/json", "X-Provider-Signature": "sha256=bad", "X-Provider-Timestamp": timestamp, "X-Provider-Nonce": nonce},
    )
    accepted = client.post(
        "/v1/filing/provider-callbacks/eri_sandbox",
        content=body,
        headers={"Content-Type": "application/json", "X-Provider-Signature": f"sha256={signature}", "X-Provider-Timestamp": timestamp, "X-Provider-Nonce": nonce},
    )
    replay = client.post(
        "/v1/filing/provider-callbacks/eri_sandbox",
        content=body,
        headers={"Content-Type": "application/json", "X-Provider-Signature": f"sha256={signature}", "X-Provider-Timestamp": timestamp, "X-Provider-Nonce": nonce},
    )

    assert invalid.status_code == 401
    assert accepted.status_code == 200, accepted.text
    assert replay.status_code == 409
    assert FILING_SUBMISSION_CACHE[submission.submission_id].submission_status == SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE
    assert "sandbox-signing-value" not in accepted.text
    assert "raw" not in accepted.text.lower()


def test_provider_diagnostics_exposes_phase11_safe_fields_and_hides_secrets(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    monkeypatch.setenv("ALLOW_SANDBOX_PROVIDER_CALLS", "true")
    monkeypatch.setenv("SECRET_BACKEND", "env")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_ID_SECRET_NAME", "SBX_ID")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME", "SBX_SECRET")
    monkeypatch.setenv("SBX_ID", "sandbox-client")
    monkeypatch.setenv("SBX_SECRET", "sandbox-credential-value")
    get_settings.cache_clear()
    save_sandbox_spec(supported_operations=["submit_return", "status_check", "callback"])
    ProviderContractTestService().run(provider="mock", mode="mock")

    response = client.get("/v1/filing/provider-diagnostics", headers=auth())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["secret_backend"] == "env"
    assert body["sandbox_configured"] is True
    assert body["sandbox_calls_allowed"] is True
    assert body["live_enabled"] is False
    assert body["live_blocked_reason"]
    assert "submit_return" in body["provider_capabilities"]
    assert "sandbox-credential-value" not in response.text
    assert "sandbox-client" not in response.text
    assert "sandbox.invalid" not in response.text


def test_live_filing_default_disabled_and_missing_approval_metadata_warns(monkeypatch):
    monkeypatch.delenv("ALLOW_LIVE_FILING", raising=False)
    get_settings.cache_clear()
    assert get_settings().allow_live_filing is False

    monkeypatch.setenv("ALLOW_LIVE_FILING", "true")
    monkeypatch.delenv("LIVE_FILING_APPROVAL_TICKET", raising=False)
    monkeypatch.delenv("LIVE_FILING_APPROVED_BY", raising=False)
    monkeypatch.delenv("LIVE_FILING_APPROVED_AT", raising=False)
    get_settings.cache_clear()

    diagnostics = ProviderDiagnosticsService().current()

    assert diagnostics.live_enabled is False
    assert "approval metadata" in (diagnostics.live_blocked_reason or "").lower()
    with pytest.raises(ValueError, match="LIVE_FILING_APPROVAL_TICKET"):
        get_settings().validate_startup()


def test_mock_provider_flow_remains_configured(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "mock")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "mock")
    monkeypatch.setenv("ALLOW_SANDBOX_PROVIDER_CALLS", "false")
    get_settings.cache_clear()

    diagnostics = ProviderDiagnosticsService().current()

    assert diagnostics.provider == "mock"
    assert diagnostics.configured is True
    assert diagnostics.sandbox_calls_allowed is False


def test_controlled_sandbox_submission_endpoint_is_blocked_when_calls_disabled(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    monkeypatch.setenv("ALLOW_SANDBOX_PROVIDER_CALLS", "false")
    monkeypatch.setenv("SECRET_BACKEND", "env")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_ID_SECRET_NAME", "SBX_ID")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME", "SBX_SECRET")
    monkeypatch.setenv("SBX_ID", "sandbox-client")
    monkeypatch.setenv("SBX_SECRET", "sandbox-credential-value")
    get_settings.cache_clear()
    save_sandbox_spec()

    package = FilingPackage(
        package_id="10000000-0000-4000-8000-000000000001",
        owner_user_id=USER_A,
        organization_id=ORG_A,
        created_by=USER_A,
        assessment_year="2026-27",
        previous_year="2025-26",
        candidate_itr="ITR-1",
        status=FilingPackageStatus.READY_FOR_CA_REVIEW,
        readiness_score=90,
        validation_run_id="20000000-0000-4000-8000-000000000001",
        computation_id="30000000-0000-4000-8000-000000000001",
    )
    export = ItrExport(
        export_id="40000000-0000-4000-8000-000000000001",
        package_id=package.package_id,
        owner_user_id=USER_A,
        organization_id=ORG_A,
        created_by=USER_A,
        assessment_year="2026-27",
        previous_year="2025-26",
        candidate_itr="ITR-1",
        status=ItrExportStatus.READY_FOR_DOWNLOAD,
        validation_result=OfficialSchemaValidationResult(candidate_itr="ITR-1", assessment_year="2026-27", status="passed"),
    )
    FILING_PACKAGE_CACHE[package.package_id] = package
    ITR_EXPORT_CACHE[export.export_id] = export

    draft = client.post("/v1/filing/submissions", headers=auth(), json={"package_id": package.package_id, "export_id": export.export_id})
    response = client.post(f"/v1/filing/submissions/{draft.json()['submission_id']}/submit", headers=auth(), json={})

    assert response.status_code == 400
    assert "blocked" in response.text.lower()
    assert "sandbox_provider_calls_disabled" in response.text

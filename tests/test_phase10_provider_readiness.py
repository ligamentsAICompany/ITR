import hashlib
import hmac
import json
import os

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.main import app
from app.models.filing_submission import FilingSubmission, SubmissionStatus
from app.models.provider_spec import AuthType, ProviderMode, ProviderSpec, SignatureType
from app.repositories.audit_repository import AUDIT_EVENT_CACHE
from app.repositories.filing_workflow_repository import FILING_SUBMISSION_CACHE
from app.repositories.provider_spec_repository import PROVIDER_CONTRACT_RESULT_CACHE, PROVIDER_SPEC_CACHE
from app.services.provider_contract_test_service import ProviderContractTestService
from app.services.provider_diagnostics_service import ProviderDiagnosticsService
from app.services.provider_payload_retention_service import ProviderPayloadRetentionService
from app.services.provider_retry_policy import ProviderRetryPolicy
from app.services.provider_signing_service import ProviderSigningService
from app.services.provider_status_mapper import ProviderStatusMapper


client = TestClient(app)


def setup_function():
    os.environ["PERSISTENCE_BACKEND"] = "memory"
    rate_limiter.clear()
    get_settings.cache_clear()
    PROVIDER_SPEC_CACHE.clear()
    PROVIDER_CONTRACT_RESULT_CACHE.clear()
    FILING_SUBMISSION_CACHE.clear()
    AUDIT_EVENT_CACHE.clear()


def teardown_function():
    rate_limiter.clear()
    get_settings.cache_clear()


def auth():
    return {
        "X-Demo-User-Id": "11111111-1111-4111-8111-111111111111",
        "X-Demo-User-Role": "admin",
        "X-Demo-Organization-Id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    }


def sandbox_spec(**updates):
    data = {
        "provider_name": "eri",
        "provider_mode": ProviderMode.SANDBOX,
        "spec_version": "sandbox-v1",
        "base_url": "https://sandbox.invalid",
        "token_url": "https://sandbox.invalid/token",
        "callback_url": "https://api.example.com/v1/filing/provider-callbacks/eri_sandbox",
        "supported_operations": ["submit_return", "status_check", "everification", "acknowledgement", "callback"],
        "auth_type": AuthType.BEARER_TOKEN,
        "signature_type": SignatureType.HMAC_SIGNATURE,
        "payload_format": "json",
        "status_mapping_version": "v1",
        "is_active": True,
    }
    data.update(updates)
    return ProviderSpec(**data)


def test_no_active_sandbox_spec_returns_not_configured(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    get_settings.cache_clear()

    diagnostics = ProviderDiagnosticsService().current()

    assert diagnostics.provider == "eri_sandbox"
    assert diagnostics.mode == "sandbox"
    assert diagnostics.configured is False
    assert diagnostics.status == "not_configured"
    assert diagnostics.live_filing_enabled is False


def test_active_mock_provider_is_configured_without_external_spec(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "mock")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "mock")
    get_settings.cache_clear()

    diagnostics = ProviderDiagnosticsService().current()

    assert diagnostics.provider == "mock"
    assert diagnostics.mode == "mock"
    assert diagnostics.configured is True
    assert "submit_return" in diagnostics.supported_operations


def test_active_sandbox_spec_without_credentials_is_blocked(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    monkeypatch.delenv("ERI_CLIENT_ID", raising=False)
    monkeypatch.delenv("ERI_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    ProviderDiagnosticsService().spec_repository.save(sandbox_spec())

    diagnostics = ProviderDiagnosticsService().current()

    assert diagnostics.configured is False
    assert diagnostics.status == "blocked"
    assert "credentials" in (diagnostics.safe_error or "").lower()


def test_live_spec_without_allow_flag_is_blocked(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_live")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_FILING", "false")
    get_settings.cache_clear()
    ProviderDiagnosticsService().spec_repository.save(sandbox_spec(provider_mode=ProviderMode.LIVE, spec_version="live-v1"))

    diagnostics = ProviderDiagnosticsService().current()

    assert diagnostics.configured is False
    assert diagnostics.live_filing_enabled is False
    assert "disabled" in (diagnostics.safe_error or "").lower()


def test_contract_tests_pass_for_mock_and_do_not_verify_missing_real_credentials(monkeypatch):
    monkeypatch.delenv("ERI_CLIENT_ID", raising=False)
    monkeypatch.delenv("ERI_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()

    mock_result = ProviderContractTestService().run(provider="mock", mode="mock")
    sandbox_result = ProviderContractTestService().run(provider="eri", mode="sandbox")

    assert mock_result.status == "passed"
    assert all(check.status == "passed" for check in mock_result.checks)
    assert sandbox_result.status == "not_verified"
    assert any("credentials" in failure.lower() for failure in sandbox_result.failures)


def test_signing_missing_config_fails_safely_and_redacts_secret(monkeypatch):
    monkeypatch.delenv("ERI_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()

    result = ProviderSigningService().sign_request(spec=sandbox_spec(), body=b'{"pan":"ABCDE1234F"}')

    assert result.success is False
    assert result.safe_error == "Provider signing configuration is missing"
    assert "ABCDE1234F" not in json.dumps(result.model_dump())
    assert "secret" not in json.dumps(result.model_dump()).lower()


def test_callback_invalid_missing_and_replayed_signatures_are_rejected(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("ALLOW_DEMO_AUTH_IN_PRODUCTION", "true")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("ERI_CLIENT_SECRET", "callback-secret")
    get_settings.cache_clear()
    submission = FilingSubmission(
        package_id="pkg-callback",
        export_id="exp-callback",
        provider_reference_id="ERI-CB-123",
        submission_status=SubmissionStatus.SUBMITTED,
    )
    FILING_SUBMISSION_CACHE[submission.submission_id] = submission
    payload = {"callback_id": "cb-1", "provider_reference_id": "ERI-CB-123", "provider_status": "verified"}
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = "2026-05-30T00:00:00Z"
    nonce = "nonce-1"
    signature = hmac.new(b"callback-secret", body + timestamp.encode() + nonce.encode(), hashlib.sha256).hexdigest()

    missing = client.post("/v1/filing/provider-callbacks/eri_sandbox", content=body, headers={"Content-Type": "application/json"})
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

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert accepted.status_code == 200, accepted.text
    assert replay.status_code == 409
    assert FILING_SUBMISSION_CACHE[submission.submission_id].submission_status == SubmissionStatus.VERIFIED
    assert "raw" not in accepted.text.lower()


def test_callback_invalid_status_transition_does_not_corrupt_submission(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("ALLOW_DEMO_AUTH_IN_PRODUCTION", "true")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("ERI_CLIENT_SECRET", "callback-secret")
    get_settings.cache_clear()
    submission = FilingSubmission(
        package_id="pkg-callback",
        export_id="exp-callback",
        provider_reference_id="ERI-CB-DRAFT",
        submission_status=SubmissionStatus.DRAFT,
    )
    FILING_SUBMISSION_CACHE[submission.submission_id] = submission
    payload = {"callback_id": "cb-draft", "provider_reference_id": "ERI-CB-DRAFT", "provider_status": "verified"}
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(b"callback-secret", body, hashlib.sha256).hexdigest()

    response = client.post(
        "/v1/filing/provider-callbacks/eri_sandbox",
        content=body,
        headers={"Content-Type": "application/json", "X-Provider-Signature": f"sha256={signature}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["normalized_status"] == "verified"
    assert FILING_SUBMISSION_CACHE[submission.submission_id].submission_status == SubmissionStatus.DRAFT


def test_retry_policy_retries_only_retryable_errors_and_maps_safe_failures():
    attempts = {"rate": 0, "invalid": 0}

    def rate_limited():
        attempts["rate"] += 1
        if attempts["rate"] < 3:
            raise TimeoutError("provider 429 rate limit token=secret ABCDE1234F")
        return "ok"

    def invalid_payload():
        attempts["invalid"] += 1
        raise ValueError("invalid payload")

    policy = ProviderRetryPolicy(retry_count=2, backoff_seconds=0)

    assert policy.run(rate_limited, operation="status_check").value == "ok"
    failed = policy.run(invalid_payload, operation="submit_return")
    assert failed.value is None
    assert failed.error_code == "INVALID_PAYLOAD"
    assert failed.retryable is False
    assert attempts["invalid"] == 1
    assert "secret" not in (failed.safe_message or "").lower()


def test_status_mapper_handles_known_unknown_and_invalid_transitions():
    mapper = ProviderStatusMapper()

    known = mapper.map_status("acknowledgement available", current_status=SubmissionStatus.VERIFIED)
    unknown = mapper.map_status("PAN ABCDE1234F backend-status", current_status=SubmissionStatus.SUBMITTED)
    invalid = mapper.map_status("pending verification", current_status=SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE)

    assert known.normalized_status == SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE
    assert known.transition_valid is True
    assert unknown.normalized_status == SubmissionStatus.PENDING_VERIFICATION
    assert unknown.raw_status_exposed is False
    assert "ABCDE1234F" not in unknown.safe_message
    assert invalid.transition_valid is False


def test_raw_payload_retention_disabled_by_default_and_never_public(monkeypatch):
    monkeypatch.delenv("STORE_PROVIDER_RAW_PAYLOADS", raising=False)
    get_settings.cache_clear()

    retained = ProviderPayloadRetentionService().retain(
        provider="eri_sandbox",
        operation="submit_return",
        payload={"pan": "ABCDE1234F", "client_secret": "secret"},
    )

    assert retained.stored is False
    assert retained.public_payload == {}
    assert "ABCDE1234F" not in json.dumps(retained.model_dump())
    assert "secret" not in json.dumps(retained.model_dump()).lower()


def test_provider_diagnostics_endpoint_returns_safe_fields(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "mock")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "mock")
    monkeypatch.setenv("ERI_CLIENT_SECRET", "super-secret")
    get_settings.cache_clear()
    ProviderContractTestService().run(provider="mock", mode="mock")

    response = client.get("/v1/filing/provider-diagnostics", headers=auth())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "mock"
    assert body["mode"] == "mock"
    assert body["configured"] is True
    assert body["live_filing_enabled"] is False
    assert body["last_contract_test"]["status"] == "passed"
    assert "super-secret" not in response.text
    assert "raw_payload" not in response.text

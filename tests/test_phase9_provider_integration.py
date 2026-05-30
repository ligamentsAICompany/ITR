import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.main import app
from app.models.filing_package import FilingPackage, FilingPackageStatus
from app.models.filing_submission import FilingSubmission, SubmissionStatus
from app.models.itr_export import ItrExport, ItrExportStatus, OfficialSchemaValidationResult
from app.models.provider_integration import ProviderCapability, ProviderMode
from app.models.provider_spec import AuthType, ProviderSpec, SignatureType
from app.repositories.audit_repository import AUDIT_EVENT_CACHE
from app.repositories.filing_package_repository import FILING_PACKAGE_CACHE
from app.repositories.filing_workflow_repository import (
    ACKNOWLEDGEMENT_CACHE,
    FILING_APPROVAL_CACHE,
    FILING_CONSENT_CACHE,
    FILING_SUBMISSION_CACHE,
)
from app.repositories.itr_export_repository import ITR_EXPORT_CACHE
from app.repositories.provider_spec_repository import PROVIDER_SPEC_CACHE, ProviderSpecRepository
from app.services.eri_provider_factory import get_eri_provider_configuration
from app.services.provider_error_mapper import ProviderErrorCode, map_provider_error, sanitize_provider_text
from app.services.provider_status_service import ProviderStatusService


client = TestClient(app)

USER_A = "11111111-1111-4111-8111-111111111111"
ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def auth():
    return {
        "X-Demo-User-Id": USER_A,
        "X-Demo-User-Role": "taxpayer",
        "X-Demo-Organization-Id": ORG_A,
    }


def setup_function():
    rate_limiter.clear()
    FILING_PACKAGE_CACHE.clear()
    ITR_EXPORT_CACHE.clear()
    FILING_CONSENT_CACHE.clear()
    FILING_APPROVAL_CACHE.clear()
    FILING_SUBMISSION_CACHE.clear()
    ACKNOWLEDGEMENT_CACHE.clear()
    AUDIT_EVENT_CACHE.clear()
    PROVIDER_SPEC_CACHE.clear()
    get_settings.cache_clear()


def teardown_function():
    rate_limiter.clear()
    get_settings.cache_clear()


def save_package_and_export():
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
        validation_result=OfficialSchemaValidationResult(
            candidate_itr="ITR-1",
            assessment_year="2026-27",
            status="passed",
        ),
    )
    FILING_PACKAGE_CACHE[package.package_id] = package
    ITR_EXPORT_CACHE[export.export_id] = export
    return package, export


def save_active_provider_spec(mode: ProviderMode = ProviderMode.SANDBOX):
    ProviderSpecRepository().save(
        ProviderSpec(
            provider_name="eri",
            provider_mode=mode,
            spec_version=f"{mode.value}-v1",
            base_url=f"https://{mode.value}.invalid",
            token_url=f"https://{mode.value}.invalid/token",
            callback_url="https://api.example.com/v1/filing/provider-callbacks/eri_sandbox",
            supported_operations=["submit_return", "status_check", "everification", "acknowledgement", "callback"],
            auth_type=AuthType.BEARER_TOKEN,
            signature_type=SignatureType.HMAC_SIGNATURE,
            payload_format="json",
            status_mapping_version="v1",
            is_active=True,
        )
    )


def test_provider_mode_models_and_default_config_are_safe(monkeypatch):
    monkeypatch.delenv("FILING_PROVIDER", raising=False)
    monkeypatch.delenv("FILING_PROVIDER_MODE", raising=False)
    get_settings.cache_clear()

    config = get_eri_provider_configuration()

    assert ProviderMode.MOCK == "mock"
    assert ProviderCapability.SUBMIT_RETURN == "submit_return"
    assert config.provider == "mock"
    assert config.mode == ProviderMode.MOCK
    assert config.configured is True
    assert config.live_allowed is False


def test_sandbox_and_live_missing_config_fail_safely(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    monkeypatch.delenv("ERI_CLIENT_ID", raising=False)
    monkeypatch.delenv("ERI_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    save_active_provider_spec()

    sandbox = get_eri_provider_configuration()
    assert sandbox.configured is False
    assert "credentials" in (sandbox.safe_error or "").lower()

    monkeypatch.setenv("FILING_PROVIDER", "eri_live")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_FILING", "false")
    get_settings.cache_clear()

    live = get_eri_provider_configuration()
    assert live.configured is False
    assert live.live_allowed is False
    assert "disabled" in (live.safe_error or "").lower()


def test_live_enabled_without_credentials_blocks_provider_call(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_live")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_FILING", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ERI_CLIENT_ID", raising=False)
    monkeypatch.delenv("ERI_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    save_active_provider_spec(ProviderMode.LIVE)

    config = get_eri_provider_configuration()

    assert config.configured is False
    assert "credentials" in (config.safe_error or "").lower()


def test_provider_error_mapping_redacts_credentials_pan_and_aadhaar():
    mapped = map_provider_error(
        "401 token=secret-token client_secret=s3cr3t PAN ABCDE1234F Aadhaar 123456789012",
        operation="submit_return",
    )

    assert mapped.code == ProviderErrorCode.AUTH_FAILED
    assert mapped.retryable is False
    assert mapped.safe_message == "Provider authentication failed. Please check secure provider configuration."
    assert "secret-token" not in mapped.audit_message
    assert "s3cr3t" not in mapped.audit_message
    assert "ABCDE1234F" not in mapped.audit_message
    assert "123456789012" not in mapped.audit_message
    assert "AB****4F" in mapped.audit_message


def test_sandbox_provider_submit_status_everification_and_ack_are_mocked(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    monkeypatch.setenv("ERI_BASE_URL", "https://sandbox.invalid")
    monkeypatch.setenv("ERI_TOKEN_URL", "https://sandbox.invalid/token")
    monkeypatch.setenv("ERI_CLIENT_ID", "sandbox-client")
    monkeypatch.setenv("ERI_CLIENT_SECRET", "sandbox-secret")
    get_settings.cache_clear()
    save_active_provider_spec()

    from app.services.eri_provider_factory import get_eri_provider

    provider = get_eri_provider()
    auth_response = provider.authenticate()
    submit_response = provider.submit_return(package_id="pkg-12345678", export_id="exp-12345678", payload=b'{"safe":true}')
    status_response = provider.get_submission_status(provider_reference_id=submit_response.provider_reference_id or "")
    everify_response = provider.initiate_everification(provider_reference_id=submit_response.provider_reference_id or "")
    ack_response = provider.get_acknowledgement(provider_reference_id=submit_response.provider_reference_id or "")

    assert auth_response.success is True
    assert submit_response.provider_reference_id
    assert submit_response.normalized_status == SubmissionStatus.SUBMITTED
    assert status_response.normalized_status == SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE
    assert everify_response.safe_message
    assert ack_response.acknowledgement_number is None
    assert ack_response.normalized_status == SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE


def test_provider_status_polling_updates_submission_and_audits(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    monkeypatch.setenv("ERI_BASE_URL", "https://sandbox.invalid")
    monkeypatch.setenv("ERI_TOKEN_URL", "https://sandbox.invalid/token")
    monkeypatch.setenv("ERI_CLIENT_ID", "sandbox-client")
    monkeypatch.setenv("ERI_CLIENT_SECRET", "sandbox-secret")
    get_settings.cache_clear()
    save_active_provider_spec()

    package, export = save_package_and_export()
    submission = FilingSubmission(
        package_id=package.package_id,
        export_id=export.export_id,
        owner_user_id=USER_A,
        organization_id=ORG_A,
        provider="eri_sandbox",
        provider_mode="sandbox",
        provider_reference_id="ERI-SANDBOX-1234",
        submission_status=SubmissionStatus.SUBMITTED,
    )
    FILING_SUBMISSION_CACHE[submission.submission_id] = submission

    updated = ProviderStatusService().poll_submission_status(submission_id=submission.submission_id)

    assert updated.submission_status == SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE
    assert updated.last_checked_at is not None
    assert any(event.event_type == "provider_status_checked" for event in AUDIT_EVENT_CACHE.values())


def test_provider_status_polling_preserves_state_on_transient_failure(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "mock")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "mock")
    monkeypatch.setenv("MOCK_FILING_OUTCOME", "failure")
    get_settings.cache_clear()

    package, export = save_package_and_export()
    submission = FilingSubmission(
        package_id=package.package_id,
        export_id=export.export_id,
        owner_user_id=USER_A,
        organization_id=ORG_A,
        provider="mock",
        provider_mode="mock",
        provider_reference_id="MOCK-1234",
        submission_status=SubmissionStatus.SUBMITTED,
    )
    FILING_SUBMISSION_CACHE[submission.submission_id] = submission

    updated = ProviderStatusService().poll_submission_status(submission_id=submission.submission_id)

    assert updated.submission_status == SubmissionStatus.SUBMITTED
    assert updated.failure_reason == "Provider status check failed"
    assert updated.last_checked_at is not None


def test_filing_status_check_preserves_state_on_provider_failure(monkeypatch):
    monkeypatch.setenv("FILING_PROVIDER", "mock")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "mock")
    monkeypatch.setenv("MOCK_FILING_OUTCOME", "failure")
    get_settings.cache_clear()

    package, export = save_package_and_export()
    submission = FilingSubmission(
        package_id=package.package_id,
        export_id=export.export_id,
        owner_user_id=USER_A,
        organization_id=ORG_A,
        provider="mock",
        provider_mode="mock",
        provider_reference_id="MOCK-1234",
        submission_status=SubmissionStatus.SUBMITTED,
    )
    FILING_SUBMISSION_CACHE[submission.submission_id] = submission

    response = client.post(f"/v1/filing/submissions/{submission.submission_id}/status-check", headers=auth(), json={})

    assert response.status_code == 200, response.text
    assert response.json()["submission_status"] == "submitted"
    assert response.json()["failure_reason"] == "Provider status check failed"


def test_callback_unsigned_rejected_in_production_and_signed_updates_status(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("ALLOW_DEMO_AUTH_IN_PRODUCTION", "true")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("ERI_CLIENT_SECRET", "callback-secret")
    get_settings.cache_clear()

    package, export = save_package_and_export()
    submission = FilingSubmission(
        package_id=package.package_id,
        export_id=export.export_id,
        owner_user_id=USER_A,
        organization_id=ORG_A,
        provider_reference_id="ERI-CB-123",
        submission_status=SubmissionStatus.SUBMITTED,
    )
    FILING_SUBMISSION_CACHE[submission.submission_id] = submission
    payload = {
        "callback_id": "cb-1",
        "event_type": "status_update",
        "provider_reference_id": "ERI-CB-123",
        "provider_status": "acknowledgement_available",
    }

    unsigned = client.post("/v1/filing/provider-callbacks/eri_sandbox", json=payload)
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(b"callback-secret", body, hashlib.sha256).hexdigest()
    signed = client.post(
        "/v1/filing/provider-callbacks/eri_sandbox",
        content=body,
        headers={"Content-Type": "application/json", "X-Provider-Signature": f"sha256={signature}"},
    )

    assert unsigned.status_code == 401
    assert signed.status_code == 200, signed.text
    assert signed.json()["verified"] is True
    assert FILING_SUBMISSION_CACHE[submission.submission_id].submission_status == SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE
    assert "provider_status" in signed.json()
    assert "raw" not in signed.text.lower()


def test_callback_rejects_unknown_provider():
    response = client.post(
        "/v1/filing/provider-callbacks/unknown_provider",
        json={"provider_reference_id": "UNKNOWN-123", "provider_status": "submitted"},
    )

    assert response.status_code == 400
    assert "Unsupported filing provider callback" in response.text


def test_sanitizer_handles_provider_payload_like_text():
    sanitized = sanitize_provider_text(
        {"token": "abc", "client_secret": "def", "message": "PAN ABCDE1234F failed for 123456789012"}
    )

    assert "abc" not in sanitized
    assert "def" not in sanitized
    assert "ABCDE1234F" not in sanitized
    assert "123456789012" not in sanitized

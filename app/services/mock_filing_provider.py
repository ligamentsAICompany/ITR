"""Mock filing provider for local and sandbox-readiness workflows."""

from app.core.config import get_settings
from app.models.filing_submission import SubmissionStatus
from app.models.provider_integration import ProviderCallbackEvent
from app.services.filing_provider import FilingProviderResponse


class MockFilingProvider:
    provider_name = "mock"

    def __init__(self, *, provider_mode: str = "mock", outcome: str | None = None) -> None:
        self.provider_mode = provider_mode
        self.outcome = (outcome or getattr(get_settings(), "mock_filing_outcome", "success")).lower()

    def authenticate(self) -> FilingProviderResponse:
        return FilingProviderResponse(success=True, status="authenticated", safe_message="Mock provider authenticated")

    def validate_submission_package(self, *, package_id: str, export_id: str) -> FilingProviderResponse:
        if self.outcome == "failure":
            return FilingProviderResponse(success=False, status="failed", failure_reason="Mock provider rejected package", safe_message="Mock provider rejected package")
        return FilingProviderResponse(success=True, status="validated", normalized_status=SubmissionStatus.READY, safe_message="Mock package validated")

    def validate_export_payload(self, *, package_id: str, export_id: str, payload: bytes | None = None) -> FilingProviderResponse:
        return self.validate_submission_package(package_id=package_id, export_id=export_id)

    def submit_return(self, *, package_id: str, export_id: str, payload: bytes | None = None) -> FilingProviderResponse:
        if self.outcome == "failure":
            return FilingProviderResponse(
                success=False,
                status="submission_failed",
                normalized_status=SubmissionStatus.SUBMISSION_FAILED,
                failure_reason="Mock provider rejected submission",
                safe_message="Mock provider rejected submission",
            )
        reference = f"MOCK-{package_id[:8]}-{export_id[:8]}"
        status = "pending" if self.outcome == "pending" else "submitted"
        normalized = SubmissionStatus.PENDING_VERIFICATION if status == "pending" else SubmissionStatus.SUBMITTED
        return FilingProviderResponse(success=True, status=status, normalized_status=normalized, provider_reference_id=reference, safe_message="Mock submission accepted")

    def get_submission_status(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.outcome == "failure":
            return FilingProviderResponse(success=False, status="submission_failed", normalized_status=SubmissionStatus.SUBMISSION_FAILED, provider_reference_id=provider_reference_id)
        status = "pending_verification" if self.outcome == "pending" else "acknowledgement_available"
        return FilingProviderResponse(success=True, status=status, normalized_status=SubmissionStatus(status), provider_reference_id=provider_reference_id)

    def initiate_everification(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.outcome == "failure":
            return FilingProviderResponse(success=False, status="failed", provider_reference_id=provider_reference_id)
        return FilingProviderResponse(success=True, status="initiated", provider_reference_id=provider_reference_id)

    def get_everification_status(self, *, provider_reference_id: str) -> FilingProviderResponse:
        status = "pending" if self.outcome == "pending" else "verified"
        return FilingProviderResponse(success=True, status=status, provider_reference_id=provider_reference_id)

    def get_acknowledgement(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.outcome == "pending":
            return FilingProviderResponse(success=False, status="unavailable", normalized_status=SubmissionStatus.PENDING_VERIFICATION, provider_reference_id=provider_reference_id)
        return FilingProviderResponse(
            success=True,
            status="available",
            normalized_status=SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE,
            provider_reference_id=provider_reference_id,
            acknowledgement_number=f"MOCK-ACK-{provider_reference_id[-8:]}",
        )

    def handle_callback(self, *, payload: dict[str, object], verified: bool) -> ProviderCallbackEvent:
        provider_reference_id = str(payload.get("provider_reference_id") or "")
        provider_status = str(payload.get("provider_status") or "status_unknown")
        normalized = _normalize_submission_status(provider_status)
        return ProviderCallbackEvent(
            callback_id=str(payload.get("callback_id") or payload.get("event_id") or "00000000-0000-4000-8000-000000000000"),
            provider=self.provider_name,
            event_type=str(payload.get("event_type") or "status_update"),
            provider_reference_id=provider_reference_id,
            verified=verified,
            provider_status=provider_status,
            normalized_status=normalized,
        )

    def supports_everification(self) -> bool:
        return True

    def supports_acknowledgement(self) -> bool:
        return True


def _normalize_submission_status(status: str) -> SubmissionStatus:
    normalized = status.lower()
    if normalized in {item.value for item in SubmissionStatus}:
        return SubmissionStatus(normalized)
    if normalized in {"available", "ack_available"}:
        return SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE
    if normalized in {"accepted", "submitted"}:
        return SubmissionStatus.SUBMITTED
    return SubmissionStatus.PENDING_VERIFICATION

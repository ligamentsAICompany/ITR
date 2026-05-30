"""Mock filing provider for local and sandbox-readiness workflows."""

from app.core.config import get_settings
from app.services.filing_provider import FilingProviderResponse


class MockFilingProvider:
    provider_name = "mock"

    def __init__(self, *, provider_mode: str = "mock", outcome: str | None = None) -> None:
        self.provider_mode = provider_mode
        self.outcome = (outcome or getattr(get_settings(), "mock_filing_outcome", "success")).lower()

    def validate_submission_package(self, *, package_id: str, export_id: str) -> FilingProviderResponse:
        if self.outcome == "failure":
            return FilingProviderResponse(success=False, status="failed", failure_reason="Mock provider rejected package")
        return FilingProviderResponse(success=True, status="validated")

    def submit_return(self, *, package_id: str, export_id: str, payload: bytes | None = None) -> FilingProviderResponse:
        if self.outcome == "failure":
            return FilingProviderResponse(success=False, status="submission_failed", failure_reason="Mock provider rejected submission")
        reference = f"MOCK-{package_id[:8]}-{export_id[:8]}"
        status = "pending" if self.outcome == "pending" else "submitted"
        return FilingProviderResponse(success=True, status=status, provider_reference_id=reference)

    def get_submission_status(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.outcome == "failure":
            return FilingProviderResponse(success=False, status="submission_failed", provider_reference_id=provider_reference_id)
        status = "pending_verification" if self.outcome == "pending" else "acknowledgement_available"
        return FilingProviderResponse(success=True, status=status, provider_reference_id=provider_reference_id)

    def initiate_everification(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.outcome == "failure":
            return FilingProviderResponse(success=False, status="failed", provider_reference_id=provider_reference_id)
        return FilingProviderResponse(success=True, status="initiated", provider_reference_id=provider_reference_id)

    def get_everification_status(self, *, provider_reference_id: str) -> FilingProviderResponse:
        status = "pending" if self.outcome == "pending" else "verified"
        return FilingProviderResponse(success=True, status=status, provider_reference_id=provider_reference_id)

    def get_acknowledgement(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.outcome == "pending":
            return FilingProviderResponse(success=False, status="unavailable", provider_reference_id=provider_reference_id)
        return FilingProviderResponse(
            success=True,
            status="available",
            provider_reference_id=provider_reference_id,
            acknowledgement_number=f"MOCK-ACK-{provider_reference_id[-8:]}",
        )

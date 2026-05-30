"""ERI provider adapter shell with safe sandbox behavior."""

from app.models.filing_submission import SubmissionStatus
from app.models.provider_integration import ProviderCallbackEvent, ProviderMode
from app.services.eri_client import EriClient, EriNetworkDisabledError
from app.services.filing_provider import FilingProviderResponse
from app.services.provider_error_mapper import map_provider_error


class EriProvider:
    provider_name = "eri"

    def __init__(self, *, mode: ProviderMode, client: EriClient, sandbox_mocked: bool = True) -> None:
        self.provider_mode = mode.value
        self.mode = mode
        self.client = client
        self.sandbox_mocked = sandbox_mocked

    def authenticate(self) -> FilingProviderResponse:
        if self.mode == ProviderMode.SANDBOX and self.sandbox_mocked:
            return FilingProviderResponse(success=True, status="authenticated", safe_message="ERI sandbox mock authenticated")
        if self.mode == ProviderMode.LIVE:
            return self._blocked("authenticate", "Live ERI transport is not enabled in Phase 9")
        try:
            self.client.request(method="POST", path="/oauth/token", payload={})
        except (EriNetworkDisabledError, NotImplementedError) as exc:
            return self._mapped_failure(exc, operation="authenticate")
        return FilingProviderResponse(success=True, status="authenticated", safe_message="ERI provider authenticated")

    def validate_submission_package(self, *, package_id: str, export_id: str) -> FilingProviderResponse:
        return self.validate_export_payload(package_id=package_id, export_id=export_id)

    def validate_export_payload(self, *, package_id: str, export_id: str, payload: bytes | None = None) -> FilingProviderResponse:
        if self.mode == ProviderMode.SANDBOX and self.sandbox_mocked:
            return FilingProviderResponse(
                success=True,
                status="validated",
                normalized_status=SubmissionStatus.READY,
                safe_message="ERI sandbox mock validated the export payload.",
            )
        return self._blocked("validate_export_payload", "Provider export validation is not configured")

    def submit_return(self, *, package_id: str, export_id: str, payload: bytes | None = None) -> FilingProviderResponse:
        if self.mode == ProviderMode.SANDBOX and self.sandbox_mocked:
            reference = f"ERI-SANDBOX-{package_id[:8]}-{export_id[:8]}"
            return FilingProviderResponse(
                success=True,
                status="submitted",
                normalized_status=SubmissionStatus.SUBMITTED,
                provider_reference_id=reference,
                raw_status_code="SANDBOX_ACCEPTED",
                safe_message="ERI sandbox mock accepted the submission. No real return was filed.",
            )
        return self._blocked("submit_return", "Provider submission is not configured")

    def get_submission_status(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.mode == ProviderMode.SANDBOX and self.sandbox_mocked:
            return FilingProviderResponse(
                success=True,
                status="acknowledgement_available",
                normalized_status=SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE,
                provider_reference_id=provider_reference_id,
                raw_status_code="SANDBOX_ACK_READY",
                safe_message="ERI sandbox mock reports acknowledgement metadata is available.",
            )
        return self._blocked("get_submission_status", "Provider status check is not configured")

    def initiate_everification(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.mode == ProviderMode.SANDBOX and self.sandbox_mocked:
            return FilingProviderResponse(
                success=True,
                status="initiated",
                provider_reference_id=provider_reference_id,
                safe_message="ERI sandbox mock initiated e-verification.",
            )
        return self._blocked("everification", "Provider e-verification is not configured")

    def get_everification_status(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.mode == ProviderMode.SANDBOX and self.sandbox_mocked:
            return FilingProviderResponse(
                success=True,
                status="pending",
                provider_reference_id=provider_reference_id,
                safe_message="ERI sandbox mock e-verification is pending.",
            )
        return self._blocked("everification_status", "Provider e-verification status is not configured")

    def get_acknowledgement(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.mode == ProviderMode.SANDBOX and self.sandbox_mocked:
            return FilingProviderResponse(
                success=True,
                status="acknowledgement_available",
                normalized_status=SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE,
                provider_reference_id=provider_reference_id,
                safe_message="ERI sandbox mock has acknowledgement metadata only; no official acknowledgement is fabricated.",
            )
        return self._blocked("get_acknowledgement", "Provider acknowledgement retrieval is not configured")

    def handle_callback(self, *, payload: dict[str, object], verified: bool) -> ProviderCallbackEvent:
        status = str(payload.get("provider_status") or payload.get("status") or "status_unknown")
        return ProviderCallbackEvent(
            callback_id=str(payload.get("callback_id") or payload.get("event_id") or "00000000-0000-4000-8000-000000000000"),
            provider=str(payload.get("provider") or self.provider_name),
            event_type=str(payload.get("event_type") or "status_update"),
            provider_reference_id=str(payload.get("provider_reference_id") or ""),
            verified=verified,
            provider_status=status,
            normalized_status=normalize_provider_status(status),
        )

    def supports_everification(self) -> bool:
        return self.mode == ProviderMode.SANDBOX and self.sandbox_mocked

    def supports_acknowledgement(self) -> bool:
        return True

    def _blocked(self, operation: str, message: str) -> FilingProviderResponse:
        return self._mapped_failure(message, operation=operation)

    def _mapped_failure(self, error: object, *, operation: str) -> FilingProviderResponse:
        mapped = map_provider_error(error, operation=operation)
        return FilingProviderResponse(
            success=False,
            status=mapped.code.value,
            normalized_status=SubmissionStatus.SUBMISSION_FAILED,
            failure_reason=mapped.safe_message,
            safe_message=mapped.safe_message,
        )


def normalize_provider_status(status: str) -> SubmissionStatus:
    normalized = status.lower().strip()
    if normalized in {item.value for item in SubmissionStatus}:
        return SubmissionStatus(normalized)
    if normalized in {"accepted", "submitted", "success"}:
        return SubmissionStatus.SUBMITTED
    if normalized in {"pending", "in_progress", "queued"}:
        return SubmissionStatus.PENDING_VERIFICATION
    if normalized in {"ack_available", "acknowledgement_ready", "acknowledgement_available", "available"}:
        return SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE
    if normalized in {"rejected", "failed", "error"}:
        return SubmissionStatus.SUBMISSION_FAILED
    return SubmissionStatus.PENDING_VERIFICATION

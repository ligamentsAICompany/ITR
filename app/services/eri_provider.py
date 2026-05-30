"""ERI provider adapter shell with safe sandbox behavior."""

from app.models.filing_submission import SubmissionStatus
from app.models.provider_integration import ProviderCallbackEvent, ProviderCapability, ProviderMode
from app.services.eri_client import EriClient
from app.services.filing_provider import FilingProviderResponse
from app.services.provider_error_mapper import map_provider_error
from app.services.provider_retry_policy import ProviderRetryPolicy


class EriProvider:
    provider_name = "eri"

    def __init__(
        self,
        *,
        mode: ProviderMode,
        client: EriClient,
        sandbox_mocked: bool = True,
        capabilities: tuple[ProviderCapability, ...] = (),
    ) -> None:
        self.provider_mode = mode.value
        self.mode = mode
        self.client = client
        self.sandbox_mocked = sandbox_mocked
        self.capabilities = capabilities

    def authenticate(self) -> FilingProviderResponse:
        if self.mode == ProviderMode.SANDBOX and self.sandbox_mocked:
            return FilingProviderResponse(success=True, status="authenticated", safe_message="ERI sandbox mock authenticated")
        if self.mode == ProviderMode.LIVE:
            return self._blocked("authenticate", "Live ERI transport is not enabled in Phase 9")
        try:
            self._request("authenticate", method="POST", path="/oauth/token", payload={})
        except Exception as exc:  # noqa: BLE001 - provider failures must map safely.
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
        if self.mode == ProviderMode.SANDBOX:
            try:
                result = self._request("validate_export_payload", method="POST", path="/validate", payload={"package_id": package_id, "export_id": export_id, "test_payload": True})
            except Exception as exc:  # noqa: BLE001
                return self._mapped_failure(exc, operation="validate_export_payload")
            if result is None:
                return self._blocked("validate_export_payload", "Provider export validation is not configured")
            return FilingProviderResponse(
                success=True,
                status=str(result.get("status") or "validated"),
                normalized_status=SubmissionStatus.READY,
                raw_status_code=_safe_str(result.get("raw_status_code")),
                safe_message="ERI sandbox validated the export payload. No real return was filed.",
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
        if self.mode == ProviderMode.SANDBOX:
            try:
                result = self._request("submit_return", method="POST", path="/submit", payload={"package_id": package_id, "export_id": export_id, "sandbox_test": True})
            except Exception as exc:  # noqa: BLE001
                return self._mapped_failure(exc, operation="submit_return")
            if result is None:
                return self._blocked("submit_return", "Provider submission is not configured")
            status = str(result.get("status") or "submitted")
            return FilingProviderResponse(
                success=True,
                status=status,
                normalized_status=normalize_provider_status(status),
                provider_reference_id=_safe_str(result.get("provider_reference_id")),
                raw_status_code=_safe_str(result.get("raw_status_code")),
                safe_message="Sandbox submission only. This is not a real tax filing.",
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
        if self.mode == ProviderMode.SANDBOX:
            try:
                result = self._request("get_submission_status", method="GET", path=f"/status/{provider_reference_id}", payload=None)
            except Exception as exc:  # noqa: BLE001
                return self._mapped_failure(exc, operation="get_submission_status")
            if result is None:
                return self._blocked("get_submission_status", "Provider status check is not configured")
            status = str(result.get("status") or "pending_verification")
            return FilingProviderResponse(
                success=True,
                status=status,
                normalized_status=normalize_provider_status(status),
                provider_reference_id=_safe_str(result.get("provider_reference_id")) or provider_reference_id,
                raw_status_code=_safe_str(result.get("raw_status_code")),
                safe_message="ERI sandbox status received. This is not a real filing status.",
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
        if not self.supports_everification():
            return self._blocked("everification", "Provider e-verification is not supported for this mode")
        result = self._request("everification", method="POST", path="/everification", payload={"provider_reference_id": provider_reference_id})
        status = str((result or {}).get("status") or "initiated")
        return FilingProviderResponse(success=True, status=status, provider_reference_id=provider_reference_id, safe_message="ERI sandbox e-verification initiated.")

    def get_everification_status(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.mode == ProviderMode.SANDBOX and self.sandbox_mocked:
            return FilingProviderResponse(
                success=True,
                status="pending",
                provider_reference_id=provider_reference_id,
                safe_message="ERI sandbox mock e-verification is pending.",
            )
        if not self.supports_everification():
            return self._blocked("everification_status", "Provider e-verification status is not supported for this mode")
        result = self._request("everification_status", method="GET", path=f"/everification/{provider_reference_id}", payload=None)
        status = str((result or {}).get("status") or "pending")
        return FilingProviderResponse(success=True, status=status, provider_reference_id=provider_reference_id, safe_message="ERI sandbox e-verification status received.")

    def get_acknowledgement(self, *, provider_reference_id: str) -> FilingProviderResponse:
        if self.mode == ProviderMode.SANDBOX and self.sandbox_mocked:
            return FilingProviderResponse(
                success=True,
                status="acknowledgement_available",
                normalized_status=SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE,
                provider_reference_id=provider_reference_id,
                safe_message="ERI sandbox mock has acknowledgement metadata only; no official acknowledgement is fabricated.",
            )
        if not self.supports_acknowledgement():
            return self._blocked("get_acknowledgement", "Provider acknowledgement retrieval is not supported for this mode")
        result = self._request("get_acknowledgement", method="GET", path=f"/acknowledgement/{provider_reference_id}", payload=None)
        if not result or not result.get("acknowledgement_number"):
            return self._blocked("get_acknowledgement", "Provider acknowledgement is unavailable in sandbox")
        return FilingProviderResponse(
            success=True,
            status="acknowledgement_available",
            normalized_status=SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE,
            provider_reference_id=provider_reference_id,
            acknowledgement_number=_safe_str(result.get("acknowledgement_number")),
            safe_message="ERI sandbox acknowledgement metadata received.",
        )

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
        return self.mode == ProviderMode.SANDBOX and (self.sandbox_mocked or ProviderCapability.EVERIFICATION in self.capabilities)

    def supports_acknowledgement(self) -> bool:
        return self.sandbox_mocked or ProviderCapability.ACKNOWLEDGEMENT in self.capabilities

    def _request(self, operation: str, *, method: str, path: str, payload: dict | None) -> dict | None:
        policy = ProviderRetryPolicy(retry_count=self.client.retry_count)
        result = policy.run(lambda: self.client.request(method=method, path=path, payload=payload), operation=operation)
        if result.value is not None:
            return result.value
        raise RuntimeError(result.safe_message or "Provider request failed")

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


def _safe_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)

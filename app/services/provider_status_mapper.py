"""Map provider statuses into internal submission states safely."""

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.filing_submission import SubmissionStatus
from app.services.provider_error_mapper import sanitize_provider_text


class ProviderStatusMappingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_status: SubmissionStatus
    safe_message: str
    transition_valid: bool
    raw_status_exposed: bool = False

    @field_validator("safe_message")
    @classmethod
    def sanitize_message(cls, value: str) -> str:
        return sanitize_provider_text(value)


class ProviderStatusMapper:
    status_mapping = {
        "accepted": SubmissionStatus.SUBMITTED,
        "submitted": SubmissionStatus.SUBMITTED,
        "success": SubmissionStatus.SUBMITTED,
        "pending verification": SubmissionStatus.PENDING_VERIFICATION,
        "pending_verification": SubmissionStatus.PENDING_VERIFICATION,
        "pending": SubmissionStatus.PENDING_VERIFICATION,
        "queued": SubmissionStatus.PENDING_VERIFICATION,
        "verified": SubmissionStatus.VERIFIED,
        "acknowledgement available": SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE,
        "acknowledgement_available": SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE,
        "ack_available": SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE,
        "available": SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE,
        "rejected": SubmissionStatus.SUBMISSION_FAILED,
        "failed": SubmissionStatus.SUBMISSION_FAILED,
        "error": SubmissionStatus.SUBMISSION_FAILED,
    }
    allowed_transitions = {
        SubmissionStatus.DRAFT: {SubmissionStatus.READY, SubmissionStatus.BLOCKED, SubmissionStatus.SUBMISSION_FAILED},
        SubmissionStatus.READY: {SubmissionStatus.SUBMITTED, SubmissionStatus.PENDING_VERIFICATION, SubmissionStatus.SUBMISSION_FAILED},
        SubmissionStatus.SUBMITTED: {SubmissionStatus.PENDING_VERIFICATION, SubmissionStatus.VERIFIED, SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE, SubmissionStatus.SUBMISSION_FAILED},
        SubmissionStatus.PENDING_VERIFICATION: {SubmissionStatus.VERIFIED, SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE, SubmissionStatus.SUBMISSION_FAILED},
        SubmissionStatus.VERIFIED: {SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE, SubmissionStatus.SUBMISSION_FAILED},
        SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE: {SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE},
        SubmissionStatus.SUBMISSION_FAILED: {SubmissionStatus.SUBMISSION_FAILED},
        SubmissionStatus.BLOCKED: {SubmissionStatus.BLOCKED, SubmissionStatus.READY},
        SubmissionStatus.CANCELLED: {SubmissionStatus.CANCELLED},
    }

    def map_status(self, raw_status: str, *, current_status: SubmissionStatus | None = None) -> ProviderStatusMappingResult:
        normalized_raw = raw_status.strip().lower().replace("-", "_")
        normalized = self.status_mapping.get(normalized_raw)
        if normalized is None:
            normalized = SubmissionStatus.PENDING_VERIFICATION
            safe_message = "Provider status is unknown. Please retry status check later."
        else:
            safe_message = f"Provider status mapped to {normalized.value.replace('_', ' ')}."
        transition_valid = True
        if current_status is not None and normalized != current_status:
            transition_valid = normalized in self.allowed_transitions.get(current_status, set())
        return ProviderStatusMappingResult(normalized_status=normalized, safe_message=safe_message, transition_valid=transition_valid)

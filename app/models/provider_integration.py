"""Safe public models for filing-provider integration state."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.filing_submission import SubmissionStatus
from app.models.validation import mask_sensitive


class ProviderMode(StrEnum):
    MOCK = "mock"
    SANDBOX = "sandbox"
    LIVE = "live"


class ProviderCapability(StrEnum):
    SUBMIT_RETURN = "submit_return"
    STATUS_CHECK = "status_check"
    EVERIFICATION = "everification"
    ACKNOWLEDGEMENT = "acknowledgement"
    CALLBACK = "callback"


class ProviderOperationStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class StrictProviderIntegrationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderRequestAudit(StrictProviderIntegrationModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    provider: str
    mode: ProviderMode
    operation: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: ProviderOperationStatus = ProviderOperationStatus.STARTED
    sanitized_error: str | None = None

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator("sanitized_error")
    @classmethod
    def sanitize_error(cls, value: str | None) -> str | None:
        return str(mask_sensitive(value)) if value is not None else None


class ProviderSubmissionResponse(StrictProviderIntegrationModel):
    provider_reference_id: str | None = None
    provider_status: str
    normalized_status: SubmissionStatus
    raw_status_code: str | None = None
    safe_message: str
    retry_after_seconds: int | None = None
    acknowledgement_number: str | None = None

    @field_validator("safe_message", "provider_status", "raw_status_code", "acknowledgement_number")
    @classmethod
    def sanitize_text(cls, value: str | None) -> str | None:
        return str(mask_sensitive(value)) if value is not None else None


class ProviderStatusResponse(StrictProviderIntegrationModel):
    provider_reference_id: str
    provider_status: str
    normalized_status: SubmissionStatus
    last_checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    safe_message: str

    @field_validator("safe_message", "provider_status")
    @classmethod
    def sanitize_text(cls, value: str) -> str:
        return str(mask_sensitive(value))


class ProviderCallbackEvent(StrictProviderIntegrationModel):
    callback_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    provider: str
    event_type: str
    provider_reference_id: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    verified: bool = False
    provider_status: str | None = None
    normalized_status: SubmissionStatus | None = None

    @field_validator("provider_status", "provider_reference_id")
    @classmethod
    def sanitize_optional_text(cls, value: str | None) -> str | None:
        return str(mask_sensitive(value)) if value is not None else None

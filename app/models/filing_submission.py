"""Filing submission, e-verification, and acknowledgement models."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.validation import mask_sensitive


class SubmissionStatus(StrEnum):
    DRAFT = "draft"
    BLOCKED = "blocked"
    READY = "ready"
    SUBMITTED = "submitted"
    SUBMISSION_FAILED = "submission_failed"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    ACKNOWLEDGEMENT_AVAILABLE = "acknowledgement_available"
    CANCELLED = "cancelled"


class EVerificationStatus(StrEnum):
    NOT_STARTED = "not_started"
    INITIATED = "initiated"
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


class StrictFilingSubmissionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FilingSubmission(StrictFilingSubmissionModel):
    submission_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_id: str
    export_id: str
    owner_user_id: str | None = None
    organization_id: str | None = None
    created_by: str | None = None
    provider: str = "mock"
    provider_mode: str = "mock"
    submission_status: SubmissionStatus = SubmissionStatus.DRAFT
    everification_status: EVerificationStatus = EVerificationStatus.NOT_STARTED
    provider_reference_id: str | None = None
    submitted_at: datetime | None = None
    last_checked_at: datetime | None = None
    failure_reason: str | None = None
    acknowledgement_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("submission_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator("failure_reason")
    @classmethod
    def mask_failure_reason(cls, value: str | None) -> str | None:
        return str(mask_sensitive(value)) if value is not None else None


class Acknowledgement(StrictFilingSubmissionModel):
    acknowledgement_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    submission_id: str
    provider_reference_id: str
    acknowledgement_number: str
    acknowledgement_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    artifact_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("acknowledgement_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return str(uuid.UUID(value))


class FilingSubmissionRequest(StrictFilingSubmissionModel):
    package_id: str
    export_id: str


class FilingExplainRequest(StrictFilingSubmissionModel):
    submission_id: str


class FilingExplanation(StrictFilingSubmissionModel):
    submission_id: str
    explanation: str
    required_actions: list[str] = Field(default_factory=list)

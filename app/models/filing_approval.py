"""Human approval gate models for government filing readiness."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.validation import mask_sensitive


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StrictFilingApprovalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FilingApproval(StrictFilingApprovalModel):
    approval_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_id: str
    export_id: str
    approver_user_id: str | None = None
    organization_id: str
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approval_notes: str | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("approval_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator("approval_notes")
    @classmethod
    def mask_notes(cls, value: str | None) -> str | None:
        return str(mask_sensitive(value)) if value is not None else None


class FilingApprovalRequest(StrictFilingApprovalModel):
    package_id: str
    export_id: str
    approval_notes: str | None = None


class FilingApprovalAction(StrictFilingApprovalModel):
    approval_notes: str | None = None

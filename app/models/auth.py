"""Strict auth and request context models for local/dev authentication."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRole(StrEnum):
    TAXPAYER = "taxpayer"
    REVIEWER = "reviewer"
    ADMIN = "admin"
    SERVICE = "service"


class StrictAuthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthUser(StrictAuthModel):
    user_id: str
    email: str | None = None
    role: UserRole
    display_name: str | None = None
    organization_id: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("user_id", "organization_id")
    @classmethod
    def validate_uuid(cls, value: str) -> str:
        return str(uuid.UUID(value))


class SessionContext(StrictAuthModel):
    session_id: str
    user_id: str
    organization_id: str
    role: UserRole
    request_id: str

    @field_validator("session_id", "user_id", "organization_id", "request_id")
    @classmethod
    def validate_uuid(cls, value: str) -> str:
        return str(uuid.UUID(value))


class AccessDecision(StrictAuthModel):
    allowed: bool
    reason: str

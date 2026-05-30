"""Privacy-safe filing consent models."""

import hashlib
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.validation import mask_sensitive


class ConsentStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    REQUESTED = "requested"
    GRANTED = "granted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class StrictFilingConsentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FilingConsent(StrictFilingConsentModel):
    consent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    organization_id: str
    package_id: str
    export_id: str
    consent_status: ConsentStatus = ConsentStatus.REQUESTED
    consent_text: str
    granted_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    ip_hash: str | None = None
    user_agent_hash: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("consent_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator("consent_text")
    @classmethod
    def validate_consent_text(cls, value: str) -> str:
        clean = str(mask_sensitive(value)).strip()
        if len(clean) < 20 or "consent" not in clean.lower():
            raise ValueError("Consent text must clearly describe the filing action")
        return clean

    @property
    def is_active(self) -> bool:
        now = datetime.now(UTC)
        return (
            self.consent_status == ConsentStatus.GRANTED
            and self.revoked_at is None
            and (self.expires_at is None or self.expires_at > now)
        )


class FilingConsentRequest(StrictFilingConsentModel):
    package_id: str
    export_id: str
    consent_text: str


class FilingConsentAction(StrictFilingConsentModel):
    pass


def hash_optional(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

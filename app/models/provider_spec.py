"""Provider specification models without secrets."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.provider_integration import ProviderCapability, ProviderMode


class AuthType(StrEnum):
    NONE = "none"
    BEARER_TOKEN = "bearer_token"
    CLIENT_SECRET = "client_secret"
    MUTUAL_TLS = "mutual_tls"


class SignatureType(StrEnum):
    NONE = "none"
    BEARER_TOKEN = "bearer_token"
    CLIENT_SECRET = "client_secret"
    MUTUAL_TLS = "mutual_tls"
    RSA_SIGNATURE = "rsa_signature"
    HMAC_SIGNATURE = "hmac_signature"


class ProviderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_spec_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    provider_name: str
    provider_mode: ProviderMode
    spec_version: str
    base_url: str | None = None
    token_url: str | None = None
    callback_url: str | None = None
    supported_operations: list[str] = Field(default_factory=list)
    auth_type: AuthType = AuthType.NONE
    signature_type: SignatureType = SignatureType.NONE
    payload_format: str = "json"
    status_mapping_version: str = "v1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = False

    @field_validator("provider_spec_id")
    @classmethod
    def validate_provider_spec_id(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator("provider_name", "spec_version", "payload_format", "status_mapping_version")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Provider spec text fields cannot be blank")
        lowered = normalized.lower()
        if any(secret_word in lowered for secret_word in ("secret", "token=", "password", "private_key")):
            raise ValueError("Provider specs cannot contain credentials or secrets")
        return normalized

    @field_validator("base_url", "token_url", "callback_url")
    @classmethod
    def validate_url_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        lowered = normalized.lower()
        if any(secret_word in lowered for secret_word in ("client_secret", "access_token", "password", "private_key")):
            raise ValueError("Provider specs cannot contain credentials or secrets")
        return normalized

    @field_validator("supported_operations")
    @classmethod
    def normalize_operations(cls, value: list[str]) -> list[str]:
        allowed = {item.value for item in ProviderCapability}
        normalized = sorted({item.strip().lower() for item in value if item.strip()})
        unsupported = [item for item in normalized if item not in allowed]
        if unsupported:
            raise ValueError(f"Unsupported provider operation: {unsupported[0]}")
        return normalized

    @model_validator(mode="after")
    def validate_mode_urls(self) -> "ProviderSpec":
        if self.provider_mode in {ProviderMode.SANDBOX, ProviderMode.LIVE} and not self.base_url:
            raise ValueError("Sandbox/live provider specs require a base URL")
        return self

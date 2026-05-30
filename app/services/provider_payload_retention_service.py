"""Safe raw provider payload retention policy."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.services.provider_error_mapper import sanitize_provider_text


class ProviderPayloadRetentionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stored: bool
    storage_status: str
    retention_days: int
    public_payload: dict[str, str] = Field(default_factory=dict)
    safe_summary: str


class ProviderPayloadRetentionService:
    def retain(self, *, provider: str, operation: str, payload: Any) -> ProviderPayloadRetentionResult:
        settings = get_settings()
        retention_days = getattr(settings, "provider_raw_payload_retention_days", 30)
        if not getattr(settings, "store_provider_raw_payloads", False):
            return ProviderPayloadRetentionResult(
                stored=False,
                storage_status="disabled",
                retention_days=retention_days,
                safe_summary="Raw provider payload retention is disabled by default.",
            )
        # Encryption-at-rest for provider payloads is intentionally not implemented in Phase 10.
        sanitized = sanitize_provider_text(payload)
        return ProviderPayloadRetentionResult(
            stored=False,
            storage_status="disabled_until_encrypted_storage",
            retention_days=retention_days,
            safe_summary=f"Raw provider payload storage requires encrypted storage before enablement. Sanitized length: {len(sanitized)}.",
        )

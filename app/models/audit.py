"""Privacy-safe audit event models."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.validation import mask_sensitive


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    actor_user_id: str
    organization_id: str
    resource_type: str
    resource_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_id: str
    ip_hash: str | None = None
    client_context: str | None = None
    metadata_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "actor_user_id", "organization_id")
    @classmethod
    def validate_uuid(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator("metadata_summary")
    @classmethod
    def sanitize_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        sanitized = mask_sensitive(value)
        return _drop_internal_paths(sanitized)


def _drop_internal_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _drop_internal_paths(item)
            for key, item in value.items()
            if key not in {"storage_path", "raw_text", "raw_document_text"}
        }
    if isinstance(value, list):
        return [_drop_internal_paths(item) for item in value]
    if isinstance(value, str) and ("\\" in value or "/" in value) and (".local_" in value or ":" in value):
        return "[internal]"
    return value

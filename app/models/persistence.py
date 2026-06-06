"""Persistence record envelopes used by repository implementations."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PersistenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    record_type: str
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

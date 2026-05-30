"""Versioned official ITR schema-pack registry models."""

import re
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.filing_package import safe_filename

ItrForm = Literal["ITR-1", "ITR-2", "ITR-3", "ITR-4"]


class SchemaPackStatus(StrEnum):
    ACCEPTED = "accepted"
    ACTIVE = "active"
    REJECTED = "rejected"


class SchemaValidationEngine(StrEnum):
    JSON_SCHEMA_DRAFT_2020_12 = "json_schema_draft_2020_12"


class StrictSchemaPackModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SchemaPack(StrictSchemaPackModel):
    assessment_year: str = Field(pattern=r"^20\d{2}-\d{2}$")
    previous_year: str | None = Field(default=None, pattern=r"^20\d{2}-\d{2}$")
    itr_form: ItrForm
    schema_pack_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str
    source_filename: str
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: SchemaPackStatus = SchemaPackStatus.ACCEPTED
    validation_engine: SchemaValidationEngine = SchemaValidationEngine.JSON_SCHEMA_DRAFT_2020_12
    is_active: bool = False

    @field_validator("schema_pack_id")
    @classmethod
    def validate_schema_pack_id(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator("source_filename")
    @classmethod
    def validate_source_filename(cls, value: str) -> str:
        safe = safe_filename(value)
        if safe != value or not safe.lower().endswith(".json"):
            raise ValueError("Schema source filename must be a safe JSON filename")
        return value

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 120 or not re.fullmatch(r"[A-Za-z0-9._:/ -]+", cleaned):
            raise ValueError("Schema version must be a short safe string")
        return cleaned


class SchemaPackUploadResponse(SchemaPack):
    pass

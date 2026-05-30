"""Document intake models for upload, extraction, and reviewed merges."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(StrEnum):
    FORM16 = "form16"
    AIS = "ais"
    BANK_STATEMENT = "bank_statement"
    PDF_TEXT = "pdf_text"
    OTHER = "other"


class StrictDocumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentRecord(StrictDocumentModel):
    document_id: str
    document_type: DocumentType
    original_filename: str
    safe_filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    sha256: str
    storage_path: str
    status: Literal["uploaded", "validated", "extracted", "rejected"] = "uploaded"


class ExtractionSource(StrictDocumentModel):
    document_id: str
    locator: str


class ExtractedField(StrictDocumentModel):
    field_id: str
    label: str
    value: str | int | float | bool
    raw_path: str
    canonical_path: str
    confidence: float = Field(ge=0, le=1)
    source: ExtractionSource


class ExtractionResult(StrictDocumentModel):
    document_id: str
    status: Literal["completed", "rejected", "warning"]
    fields: list[ExtractedField] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MergeExtractionRequest(StrictDocumentModel):
    current_payload: dict[str, Any]
    extraction_result: ExtractionResult
    approved_field_ids: list[str] = Field(default_factory=list)


class MergeExtractionResult(StrictDocumentModel):
    merged_payload: dict[str, Any]
    applied_field_ids: list[str] = Field(default_factory=list)
    skipped_field_ids: list[str] = Field(default_factory=list)

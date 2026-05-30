"""Document intake models for upload, extraction, and reviewed merges."""

from enum import StrEnum
from datetime import UTC, datetime
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
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_public_metadata(self) -> "PublicDocumentMetadata":
        return PublicDocumentMetadata(
            document_id=self.document_id,
            document_type=self.document_type,
            original_filename=self.original_filename,
            safe_filename=self.safe_filename,
            size=self.size_bytes,
            mime_type=self.content_type,
            sha256=self.sha256,
            status=self.status,
            uploaded_at=self.uploaded_at,
        )


class PublicDocumentMetadata(StrictDocumentModel):
    document_id: str
    document_type: DocumentType
    original_filename: str
    safe_filename: str
    size: int = Field(ge=0)
    mime_type: str
    sha256: str
    status: Literal["uploaded", "validated", "extracted", "rejected"] = "uploaded"
    uploaded_at: datetime


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

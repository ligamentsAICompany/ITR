"""Validation and reconciliation models for Phase 2."""

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.document import ExtractionResult, PublicDocumentMetadata
from app.models.tax_profile import CanonicalTaxProfile


class ValidationSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ValidationStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class StrictValidationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidationIssue(StrictValidationModel):
    issue_id: str
    rule_id: str
    severity: ValidationSeverity
    status: ValidationStatus
    title: str
    message: str
    field_path: str
    expected_value: Any | None = None
    actual_value: Any | None = None
    source_documents: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    recommendation: str
    blocks_filing_package: bool = False

    @field_validator("title", "message", "recommendation")
    @classmethod
    def mask_sensitive_text(cls, value: str) -> str:
        return mask_sensitive(value)

    @field_validator("expected_value", "actual_value")
    @classmethod
    def mask_sensitive_values(cls, value: Any) -> Any:
        return mask_sensitive(value)


class ReconciliationConflict(StrictValidationModel):
    field_path: str
    profile_value: Any | None = None
    extracted_value: Any | None = None
    source_documents: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_confidences: list[float] = Field(default_factory=list)

    @field_validator("profile_value", "extracted_value")
    @classmethod
    def mask_sensitive_values(cls, value: Any) -> Any:
        return mask_sensitive(value)


class ValidationEvidenceSummary(StrictValidationModel):
    document_count: int = Field(ge=0)
    approved_extracted_field_count: int = Field(ge=0)
    document_types: list[str] = Field(default_factory=list)


class ValidationReport(StrictValidationModel):
    validation_run_id: str
    profile_id: str | None = None
    session_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    overall_status: ValidationStatus
    readiness_score: int = Field(ge=0, le=100)
    issues: list[ValidationIssue] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    conflicts: list[ReconciliationConflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence_summary: ValidationEvidenceSummary


class ValidationRunRequest(StrictValidationModel):
    profile_id: str | None = None
    session_id: str | None = None
    profile: CanonicalTaxProfile
    documents: list[PublicDocumentMetadata] = Field(default_factory=list)
    extractions: list[ExtractionResult] = Field(default_factory=list)
    approved_field_ids: list[str] = Field(default_factory=list)


class ValidationExplainRequest(StrictValidationModel):
    validation_run_id: str


class ValidationExplainResponse(StrictValidationModel):
    validation_run_id: str
    explanation: str
    grounded_issue_ids: list[str] = Field(default_factory=list)

    @field_validator("explanation")
    @classmethod
    def mask_sensitive_text(cls, value: str) -> str:
        return mask_sensitive(value)

    @model_validator(mode="after")
    def reject_itr_advice(self) -> "ValidationExplainResponse":
        lowered = self.explanation.lower()
        if "should file" in lowered or "must file" in lowered or "itr-" in lowered:
            self.explanation = "Validation findings need review based only on the listed deterministic issues."
        return self


PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AADHAAR_RE = re.compile(r"\b[0-9]{12}\b")


def mask_sensitive(value: Any) -> Any:
    if isinstance(value, str):
        return AADHAAR_RE.sub("************", PAN_RE.sub(mask_pan, value))
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    if isinstance(value, dict):
        return {key: mask_sensitive(item) for key, item in value.items()}
    return value


def mask_pan(match: re.Match[str]) -> str:
    pan = match.group(0)
    return f"{pan[:2]}****{pan[-2:]}"

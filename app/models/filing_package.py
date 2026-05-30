"""Strict internal filing package models for Phase 4."""

import re
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.decision import ITRDecisionResponse
from app.models.document import PublicDocumentMetadata
from app.models.tax_computation import TaxComputationResult
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport, mask_sensitive


class FilingPackageStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    READY_FOR_CA_REVIEW = "ready_for_ca_review"
    READY_FOR_EXPORT = "ready_for_export"
    BLOCKED = "blocked"


class FilingPackageArtifactType(StrEnum):
    FILING_SUMMARY_JSON = "filing_summary_json"
    TAX_COMPUTATION_REPORT = "tax_computation_report"
    VALIDATION_REPORT_JSON = "validation_report_json"
    DRAFT_ITR_PAYLOAD = "draft_itr_payload"
    PACKAGE_MANIFEST = "package_manifest"


class StrictFilingPackageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FilingPackageWarning(StrictFilingPackageModel):
    warning_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    severity: Literal["critical", "high", "medium", "low", "info"]
    message: str
    source: str
    recommendation: str

    @field_validator("warning_id")
    @classmethod
    def validate_warning_id(cls, value: str) -> str:
        uuid.UUID(value)
        return value

    @field_validator("message", "recommendation")
    @classmethod
    def mask_text(cls, value: str) -> str:
        return str(mask_sensitive(value))


class FilingPackageArtifact(StrictFilingPackageModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_type: FilingPackageArtifactType
    filename: str
    mime_type: str
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("artifact_id")
    @classmethod
    def validate_artifact_id(cls, value: str) -> str:
        uuid.UUID(value)
        return value

    @field_validator("filename")
    @classmethod
    def validate_safe_filename(cls, value: str) -> str:
        if value != safe_filename(value):
            raise ValueError("Artifact filename must be safe")
        if _contains_sensitive_identifier(value):
            raise ValueError("Artifact filename cannot contain PAN or Aadhaar")
        return value


class FilingPackage(StrictFilingPackageModel):
    package_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_year: str
    previous_year: str | None = None
    candidate_itr: str
    status: FilingPackageStatus
    readiness_score: int = Field(ge=0, le=100)
    validation_run_id: str
    computation_id: str
    document_ids: list[str] = Field(default_factory=list)
    warnings: list[FilingPackageWarning] = Field(default_factory=list)
    artifacts: list[FilingPackageArtifact] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("package_id")
    @classmethod
    def validate_package_id(cls, value: str) -> str:
        uuid.UUID(value)
        return value


class FilingPackageGenerateRequest(StrictFilingPackageModel):
    profile: CanonicalTaxProfile
    candidate_itr: ITRDecisionResponse
    validation_report: ValidationReport
    tax_computation_result: TaxComputationResult
    documents: list[PublicDocumentMetadata] = Field(default_factory=list)
    extracted_evidence_summary: dict[str, Any] = Field(default_factory=dict)


class FilingPackageExplainRequest(StrictFilingPackageModel):
    package_id: str


class FilingPackageExplanation(StrictFilingPackageModel):
    package_id: str
    explanation: str
    grounded_artifact_ids: list[str] = Field(default_factory=list)

    @field_validator("explanation")
    @classmethod
    def mask_explanation(cls, value: str) -> str:
        return str(mask_sensitive(value))


PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AADHAAR_RE = re.compile(r"\b[0-9]{12}\b")


def safe_filename(filename: str) -> str:
    base = filename.strip().replace("\\", "/").split("/")[-1] or "artifact.json"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-")
    return safe or "artifact.json"


def _contains_sensitive_identifier(value: str) -> bool:
    return bool(PAN_RE.search(value) or AADHAAR_RE.search(value))

"""Strict public models for official ITR export validation."""

import re
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.decision import ITRDecisionResponse
from app.models.filing_package import safe_filename
from app.models.tax_computation import TaxComputationResult
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport, mask_sensitive


class ItrExportStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    DRAFT = "draft"
    SCHEMA_FAILED = "schema_failed"
    SCHEMA_PASSED = "schema_passed"
    READY_FOR_DOWNLOAD = "ready_for_download"
    BLOCKED = "blocked"


class OfficialSchemaValidationStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    FAILED = "failed"
    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"


class ItrExportArtifactType(StrEnum):
    OFFICIAL_ITR_JSON = "official_itr_json"


class StrictItrExportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OfficialSchemaValidationError(StrictItrExportModel):
    code: str
    message: str
    field_path: str | None = None
    schema_path: str | None = None
    severity: Literal["critical", "high", "medium", "low", "info"] = "high"

    @field_validator("message")
    @classmethod
    def mask_message(cls, value: str) -> str:
        return str(mask_sensitive(value))


class OfficialSchemaValidationResult(StrictItrExportModel):
    validation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_pack_id: str | None = None
    candidate_itr: str
    assessment_year: str
    status: OfficialSchemaValidationStatus
    errors: list[OfficialSchemaValidationError] = Field(default_factory=list)
    warnings: list[OfficialSchemaValidationError] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("validation_id")
    @classmethod
    def validate_validation_id(cls, value: str) -> str:
        return str(uuid.UUID(value))


class ItrExportArtifact(StrictItrExportModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_type: ItrExportArtifactType
    filename: str
    mime_type: str = "application/json"
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("artifact_id")
    @classmethod
    def validate_artifact_id(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if value != safe_filename(value):
            raise ValueError("Artifact filename must be safe")
        if re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b|\b[0-9]{12}\b", value):
            raise ValueError("Artifact filename cannot contain PAN or Aadhaar")
        return value


class ItrExport(StrictItrExportModel):
    export_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_id: str | None = None
    owner_user_id: str | None = None
    organization_id: str | None = None
    created_by: str | None = None
    assessment_year: str
    previous_year: str | None = None
    candidate_itr: str
    schema_pack_id: str | None = None
    status: ItrExportStatus
    validation_result: OfficialSchemaValidationResult
    artifacts: list[ItrExportArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("export_id")
    @classmethod
    def validate_export_id(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator("warnings")
    @classmethod
    def mask_warnings(cls, value: list[str]) -> list[str]:
        return [str(mask_sensitive(item)) for item in value]


class ItrExportGenerateRequest(StrictItrExportModel):
    package_id: str | None = None
    profile: CanonicalTaxProfile | None = None
    candidate_itr: ITRDecisionResponse | None = None
    validation_report: ValidationReport | None = None
    tax_computation_result: TaxComputationResult | None = None


class ItrExportValidateRequest(StrictItrExportModel):
    profile: CanonicalTaxProfile
    candidate_itr: ITRDecisionResponse
    validation_report: ValidationReport
    tax_computation_result: TaxComputationResult


class ItrExportExplainRequest(StrictItrExportModel):
    export_id: str


class ItrExportExplanation(StrictItrExportModel):
    export_id: str
    validation_id: str
    explanation: str
    grounded_error_codes: list[str] = Field(default_factory=list)

    @field_validator("explanation")
    @classmethod
    def mask_explanation(cls, value: str) -> str:
        return str(mask_sensitive(value))

    @model_validator(mode="after")
    def reject_filing_claims(self) -> "ItrExportExplanation":
        forbidden = ("filed", "submitted", "accepted", "acknowledgement", "e-verified")
        if any(term in self.explanation.lower() for term in forbidden):
            self.explanation = "Schema validation results are available for review. This does not mean the return was filed or accepted."
        return self


def public_export_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Mask sensitive identifiers before an export artifact is serialized."""
    sanitized = mask_sensitive(payload)
    if isinstance(sanitized, dict):
        sanitized.pop("pan", None)
        sanitized.pop("aadhaar_number", None)
        sanitized.pop("aadhaar", None)
    return sanitized

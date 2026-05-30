"""Deterministic JSON Schema validation for generated ITR export payloads."""

from typing import Any

from jsonschema import Draft202012Validator

from app.models.itr_export import OfficialSchemaValidationResult, OfficialSchemaValidationStatus
from app.models.schema_pack import SchemaPack
from app.services.official_schema_error_mapper import OfficialSchemaErrorMapper


class OfficialSchemaValidationService:
    def __init__(self, error_mapper: OfficialSchemaErrorMapper | None = None) -> None:
        self.error_mapper = error_mapper or OfficialSchemaErrorMapper()

    def not_configured(self, *, candidate_itr: str, assessment_year: str) -> OfficialSchemaValidationResult:
        return OfficialSchemaValidationResult(
            candidate_itr=candidate_itr,
            assessment_year=assessment_year,
            status=OfficialSchemaValidationStatus.NOT_CONFIGURED,
            errors=[
                {
                    "code": "schema_pack_not_configured",
                    "message": "No active schema pack is configured for this ITR form and assessment year.",
                    "field_path": None,
                    "schema_path": None,
                    "severity": "critical",
                }
            ],
        )

    def mapping_failed(
        self,
        *,
        schema_pack: SchemaPack,
        candidate_itr: str,
        assessment_year: str,
        errors: list[dict[str, Any]],
        warnings: list[dict[str, Any]] | None = None,
    ) -> OfficialSchemaValidationResult:
        return OfficialSchemaValidationResult(
            schema_pack_id=schema_pack.schema_pack_id,
            candidate_itr=candidate_itr,
            assessment_year=assessment_year,
            status=OfficialSchemaValidationStatus.NEEDS_REVIEW,
            errors=errors,
            warnings=warnings or [],
        )

    def validate(
        self,
        *,
        schema_pack: SchemaPack,
        schema: dict[str, Any],
        payload: dict[str, Any],
        candidate_itr: str,
        assessment_year: str,
    ) -> OfficialSchemaValidationResult:
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
        mapped = [self.error_mapper.map(error) for error in errors]
        return OfficialSchemaValidationResult(
            schema_pack_id=schema_pack.schema_pack_id,
            candidate_itr=candidate_itr,
            assessment_year=assessment_year,
            status=OfficialSchemaValidationStatus.FAILED if mapped else OfficialSchemaValidationStatus.PASSED,
            errors=mapped,
            warnings=[],
        )

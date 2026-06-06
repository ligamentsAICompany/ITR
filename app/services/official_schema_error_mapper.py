"""Map JSON Schema validation errors into privacy-safe export errors."""

from jsonschema import ValidationError

from app.models.itr_export import OfficialSchemaValidationError


class OfficialSchemaErrorMapper:
    def map(self, error: ValidationError) -> OfficialSchemaValidationError:
        validator = str(error.validator)
        code = self._code(validator)
        field_path = ".".join(str(part) for part in error.path) or None
        schema_path = ".".join(str(part) for part in error.schema_path) or None
        return OfficialSchemaValidationError(
            code=code,
            message=self._message(error, code, field_path),
            field_path=field_path,
            schema_path=schema_path,
            severity="high" if code != "unsupported_field" else "medium",
        )

    def _code(self, validator: str) -> str:
        if validator == "required":
            return "missing_required"
        if validator == "type":
            return "type_mismatch"
        if validator == "enum":
            return "invalid_enum"
        if validator == "additionalProperties":
            return "unsupported_field"
        return f"schema_{validator}"

    def _message(self, error: ValidationError, code: str, field_path: str | None) -> str:
        location = field_path or "payload"
        if code == "missing_required":
            return f"A required schema field is missing at {location}."
        if code == "type_mismatch":
            return f"The value at {location} does not match the configured schema type."
        if code == "invalid_enum":
            return f"The value at {location} is not one of the configured schema choices."
        if code == "unsupported_field":
            return f"The payload contains a field not allowed by the configured schema at {location}."
        return f"The configured schema rejected {location}."

"""Schema-driven deterministic mappers for ITR export payloads."""

from copy import deepcopy
from decimal import Decimal
from typing import Any

from app.models.decision import ITRDecisionResponse
from app.models.itr_export import OfficialSchemaValidationError, public_export_payload
from app.models.tax_computation import TaxComputationResult
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport


class ItrExportMappingResult:
    def __init__(
        self,
        *,
        payload: dict[str, Any],
        errors: list[OfficialSchemaValidationError] | None = None,
        warnings: list[OfficialSchemaValidationError] | None = None,
    ) -> None:
        self.payload = payload
        self.errors = errors or []
        self.warnings = warnings or []


class ItrExportMapper:
    def map(
        self,
        *,
        profile: CanonicalTaxProfile,
        candidate_itr: ITRDecisionResponse,
        validation_report: ValidationReport,
        tax_computation_result: TaxComputationResult,
        schema: dict[str, Any],
    ) -> ItrExportMappingResult:
        source = self._source_values(profile, candidate_itr, validation_report, tax_computation_result)
        payload: dict[str, Any] = {}
        errors: list[OfficialSchemaValidationError] = []
        warnings: list[OfficialSchemaValidationError] = []
        field_map = schema.get("x-itr-field-map") if isinstance(schema.get("x-itr-field-map"), dict) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = set(schema.get("required") or [])

        for target_field in properties:
            source_path = field_map.get(target_field, target_field)
            if not isinstance(source_path, str):
                continue
            value = _get_path(source, source_path)
            if value is None:
                if target_field in required:
                    errors.append(_mapping_error(target_field))
                continue
            payload[target_field] = _json_value(value)

        for target_field in required:
            if target_field not in payload:
                errors.append(_mapping_error(str(target_field)))

        unsupported = unsupported_schedule_warnings(profile)
        warnings.extend(unsupported)
        return ItrExportMappingResult(payload=public_export_payload(payload), errors=_dedupe(errors), warnings=warnings)

    def _source_values(
        self,
        profile: CanonicalTaxProfile,
        candidate_itr: ITRDecisionResponse,
        validation_report: ValidationReport,
        tax_computation_result: TaxComputationResult,
    ) -> dict[str, Any]:
        profile_payload = deepcopy(profile.model_dump(mode="json"))
        tax_payload = deepcopy(tax_computation_result.model_dump(mode="json"))
        return {
            "profile": profile_payload,
            "decision": candidate_itr.model_dump(mode="json"),
            "validation": validation_report.model_dump(mode="json"),
            "tax": tax_payload,
            "assessment_year": profile.assessment_year,
            "previous_year": profile.previous_year,
            "itr_form": candidate_itr.candidate_itr,
            "candidate_itr": candidate_itr.candidate_itr,
            "taxable_income": tax_computation_result.taxable_income,
            "total_tax_liability": tax_computation_result.total_tax_liability,
            "refund_due": tax_computation_result.refund_due,
            "tax_payable": tax_computation_result.tax_payable,
            "gross_total_income": tax_computation_result.income.gross_total_income,
            "salary_income": tax_computation_result.income.salary_income,
            "business_profession_income": tax_computation_result.income.business_profession_income,
            "capital_gains_income": tax_computation_result.income.capital_gains_income,
            "other_sources_income": tax_computation_result.income.other_sources_income,
            "tds_salary": tax_computation_result.credits.tds_salary,
            "tds_other": tax_computation_result.credits.tds_other,
            "tcs": tax_computation_result.credits.tcs,
            "selected_regime": tax_computation_result.selected_regime,
        }


def mapper_for_itr(_itr_form: str) -> ItrExportMapper:
    return ItrExportMapper()


def _get_path(source: dict[str, Any], path: str) -> Any:
    current: Any = source
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return None
    return current


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _mapping_error(target_field: str) -> OfficialSchemaValidationError:
    return OfficialSchemaValidationError(
        code="missing_mapping",
        message=f"No deterministic mapping is available for required schema field {target_field}.",
        field_path=target_field,
        schema_path=f"required.{target_field}",
        severity="critical",
    )


def _dedupe(errors: list[OfficialSchemaValidationError]) -> list[OfficialSchemaValidationError]:
    seen: set[tuple[str, str | None]] = set()
    deduped: list[OfficialSchemaValidationError] = []
    for error in errors:
        key = (error.code, error.field_path)
        if key not in seen:
            seen.add(key)
            deduped.append(error)
    return deduped


def unsupported_schedule_warnings(profile: CanonicalTaxProfile) -> list[OfficialSchemaValidationError]:
    warnings: list[OfficialSchemaValidationError] = []
    if profile.foreign_assets.has_foreign_assets == "yes" or profile.foreign_assets.has_foreign_income == "yes":
        warnings.append(
            OfficialSchemaValidationError(
                code="unsupported_schedule",
                message="Foreign asset or foreign income schedules are not mapped in this export mapper.",
                field_path="foreign_assets",
                schema_path=None,
                severity="medium",
            )
        )
    return warnings

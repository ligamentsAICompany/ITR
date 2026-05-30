"""Pure deterministic validation rules for Phase 2."""

from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from app.models.document import ExtractedField, PublicDocumentMetadata
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import (
    ReconciliationConflict,
    ValidationIssue,
    ValidationSeverity,
    ValidationStatus,
)


SEVERITY_DEDUCTIONS = {
    ValidationSeverity.CRITICAL: 35,
    ValidationSeverity.HIGH: 20,
    ValidationSeverity.MEDIUM: 10,
    ValidationSeverity.LOW: 3,
    ValidationSeverity.INFO: 0,
}


def compute_readiness_score(issues: Iterable[ValidationIssue]) -> int:
    score = 100 - sum(SEVERITY_DEDUCTIONS[issue.severity] for issue in issues)
    return max(0, min(100, score))


def compute_overall_status(issues: list[ValidationIssue]) -> ValidationStatus:
    severities = {issue.severity for issue in issues}
    if ValidationSeverity.CRITICAL in severities:
        return ValidationStatus.FAILED
    if ValidationSeverity.HIGH in severities:
        return ValidationStatus.NEEDS_REVIEW
    if ValidationSeverity.MEDIUM in severities or ValidationSeverity.LOW in severities:
        return ValidationStatus.WARNING
    return ValidationStatus.PASSED


def run_profile_rules(
    *,
    profile: CanonicalTaxProfile,
    documents: list[PublicDocumentMetadata],
    approved_fields: list[ExtractedField],
) -> tuple[list[ValidationIssue], list[str]]:
    issues: list[ValidationIssue] = []
    missing_fields: list[str] = []
    doc_types = {document.document_type for document in documents}
    filenames = " ".join(document.safe_filename.lower() for document in documents)

    for document in documents:
        if document.status == "rejected":
            issues.append(
                issue(
                    "documents.unsafe_state",
                    ValidationSeverity.CRITICAL,
                    "Unsafe document state",
                    f"Document {document.document_id} is rejected and cannot be trusted for validation.",
                    "documents",
                    "Remove or replace the rejected document before preparing any filing package.",
                    source_documents=[document.document_id],
                    blocks=True,
                )
            )

    expected_previous_year = previous_year_for_assessment(profile.assessment_year)
    if profile.previous_year and expected_previous_year and profile.previous_year != expected_previous_year:
        issues.append(
            issue(
                "period.ay_py_mismatch",
                ValidationSeverity.HIGH,
                "Assessment year and previous year mismatch",
                "The assessment year does not line up with the declared previous year.",
                "previous_year",
                "Review the year pair before relying on validation or ITR recommendation.",
                expected=expected_previous_year,
                actual=profile.previous_year,
                status=ValidationStatus.NEEDS_REVIEW,
            )
        )

    if profile.user_identity.aadhaar_last4 and not profile.user_identity.aadhaar_number:
        issues.append(
            issue(
                "identity.aadhaar_presence_review",
                ValidationSeverity.INFO,
                "Aadhaar partially supplied",
                "Only Aadhaar last four digits are present; full Aadhaar is optional but must be user-entered if used.",
                "user_identity.aadhaar_last4",
                "Continue if Aadhaar is not required for this validation step.",
                status=ValidationStatus.PASSED,
            )
        )

    salary_amount = money(profile.income_heads.salary.gross_amount)
    if is_yes(profile.income_heads.salary.has_income) or salary_amount > 0:
        if "form16" not in doc_types:
            missing_fields.append("documents.form16")
            issues.append(
                issue(
                    "documents.missing_form16_salary",
                    ValidationSeverity.MEDIUM,
                    "Missing Form 16 for salary evidence",
                    "Salary is declared, but no Form 16 document is available for evidence-based validation.",
                    "income_heads.salary.gross_amount",
                    "Upload Form 16 or manually review salary before filing.",
                )
            )

    tds_total = money(profile.tax_payments.tds_salary) + money(profile.tax_payments.tds_other)
    has_ais_or_26as = "ais" in doc_types or "26as" in filenames
    if tds_total > 0 and not has_ais_or_26as:
        missing_fields.append("documents.ais_or_26as")
        issues.append(
            issue(
                "documents.missing_ais_26as_tds",
                ValidationSeverity.MEDIUM,
                "Missing AIS or 26AS for TDS evidence",
                "TDS is declared, but no AIS or Form 26AS evidence is available.",
                "tax_payments",
                "Upload AIS or 26AS before relying on TDS reconciliation.",
            )
        )

    deductions = profile.deductions.section_claims
    deduction_total = sum(money(claim.amount) for claim in deductions)
    has_deduction_evidence = any(field.canonical_path.startswith("deductions.") for field in approved_fields)
    if (is_yes(profile.deductions.has_deductions) or deduction_total > 0) and not has_deduction_evidence:
        issues.append(
            issue(
                "evidence.deduction_missing",
                ValidationSeverity.MEDIUM,
                "Deduction evidence is missing",
                "One or more deductions are claimed, but no approved extraction supports the deduction evidence.",
                "deductions.section_claims",
                "Attach or review deduction proof before filing.",
            )
        )

    capital_gains = profile.income_heads.capital_gains
    capital_amount = (
        money(capital_gains.gross_amount)
        + money(capital_gains.stcg_amount)
        + money(capital_gains.ltcg_112a_amount)
        + money(capital_gains.other_ltcg_amount)
    )
    has_capital_evidence = any("capital_gains" in field.canonical_path for field in approved_fields)
    if (is_yes(capital_gains.has_income) or capital_amount > 0) and not has_capital_evidence:
        issues.append(
            issue(
                "evidence.capital_gains_missing",
                ValidationSeverity.MEDIUM,
                "Capital gains support is missing",
                "Capital gains are declared, but no broker statement or approved evidence supports the amount.",
                "income_heads.capital_gains",
                "Upload a capital gains statement or review the entries manually.",
            )
        )

    house_property = profile.income_heads.house_property
    if is_yes(house_property.has_income) and (
        house_property.property_count is None
        or house_property.has_self_occupied_property in {None, "unknown"}
        or house_property.has_let_out_property in {None, "unknown"}
    ):
        issues.append(
            issue(
                "profile.house_property_incomplete",
                ValidationSeverity.MEDIUM,
                "House property details are incomplete",
                "House property income is declared, but property count or occupancy details are incomplete.",
                "income_heads.house_property",
                "Review house property details before filing.",
            )
        )

    if is_yes(profile.foreign_assets.has_foreign_assets) or is_yes(profile.foreign_assets.has_foreign_income):
        issues.append(
            issue(
                "review.foreign_assets_income",
                ValidationSeverity.HIGH,
                "Foreign assets or income need expert review",
                "Foreign asset or foreign income reporting is present and needs CA review.",
                "foreign_assets",
                "Get expert review before filing.",
                status=ValidationStatus.NEEDS_REVIEW,
            )
        )

    business = profile.income_heads.business_profession
    if (is_yes(business.has_income) or money(business.gross_amount) > 0) and (
        business.nature in {None, "unknown"} or business.presumptive_taxation == "unknown"
    ):
        issues.append(
            issue(
                "profile.business_income_core_details_missing",
                ValidationSeverity.HIGH,
                "Business income core details are missing",
                "Business or professional income is present, but nature or presumptive-taxation status is unresolved.",
                "income_heads.business_profession",
                "Resolve business income details before filing.",
                status=ValidationStatus.NEEDS_REVIEW,
            )
        )

    if is_yes(profile.special_conditions.evidence_mismatch):
        issues.append(
            issue(
                "evidence.mismatch_flag",
                ValidationSeverity.HIGH,
                "Evidence mismatch flagged",
                "The profile contains an evidence mismatch flag that needs user review.",
                "special_conditions.evidence_mismatch",
                "Review conflicting evidence before continuing.",
                status=ValidationStatus.NEEDS_REVIEW,
            )
        )

    if is_yes(profile.special_conditions.low_confidence_extraction):
        issues.append(
            issue(
                "evidence.low_confidence_extraction",
                ValidationSeverity.LOW,
                "Low confidence extraction needs review",
                "One or more extracted values were marked low confidence.",
                "special_conditions.low_confidence_extraction",
                "Review the extracted evidence manually.",
            )
        )

    return issues, list(dict.fromkeys(missing_fields))


def compare_approved_fields(
    *,
    profile: CanonicalTaxProfile,
    approved_fields: list[ExtractedField],
) -> tuple[list[ValidationIssue], list[ReconciliationConflict]]:
    issues: list[ValidationIssue] = []
    conflicts: list[ReconciliationConflict] = []

    for field in approved_fields:
        profile_value = value_at_path(profile, field.canonical_path)
        if profile_value is None:
            continue
        if not values_match(profile_value, field.value):
            rule_id, severity, title = mismatch_policy(field.canonical_path)
            status = ValidationStatus.NEEDS_REVIEW if severity in {ValidationSeverity.HIGH, ValidationSeverity.CRITICAL} else ValidationStatus.WARNING
            conflicts.append(
                ReconciliationConflict(
                    field_path=field.canonical_path,
                    profile_value=profile_value,
                    extracted_value=field.value,
                    source_documents=[field.source.document_id],
                    evidence_refs=[field.source.locator],
                )
            )
            message = f"Approved evidence for {human_field(field.canonical_path)} differs from the canonical profile."
            if field.canonical_path == "user_identity.pan":
                message = f"Profile PAN {profile_value} differs from approved evidence PAN {field.value}."
            issues.append(
                issue(
                    rule_id,
                    severity,
                    title,
                    message,
                    field.canonical_path,
                    "Review the profile value against the approved document evidence; do not auto-correct it.",
                    expected=profile_value,
                    actual=field.value,
                    source_documents=[field.source.document_id],
                    evidence_refs=[field.source.locator],
                    status=status,
                    blocks=severity == ValidationSeverity.CRITICAL,
                )
            )

    return issues, conflicts


def approved_extracted_fields(extractions: list[Any], approved_field_ids: list[str]) -> list[ExtractedField]:
    approved = set(approved_field_ids)
    fields: list[ExtractedField] = []
    for extraction in extractions:
        for field in extraction.fields:
            if field.field_id in approved:
                fields.append(field)
    return fields


def issue(
    rule_id: str,
    severity: ValidationSeverity,
    title: str,
    message: str,
    field_path: str,
    recommendation: str,
    *,
    expected: Any | None = None,
    actual: Any | None = None,
    source_documents: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    status: ValidationStatus | None = None,
    blocks: bool = False,
) -> ValidationIssue:
    return ValidationIssue(
        issue_id=f"{rule_id}:{uuid4().hex[:8]}",
        rule_id=rule_id,
        severity=severity,
        status=status or (ValidationStatus.FAILED if blocks else ValidationStatus.WARNING),
        title=title,
        message=message,
        field_path=field_path,
        expected_value=expected,
        actual_value=actual,
        source_documents=source_documents or [],
        evidence_refs=evidence_refs or [],
        recommendation=recommendation,
        blocks_filing_package=blocks,
    )


def previous_year_for_assessment(assessment_year: str) -> str | None:
    try:
        first_year = int(assessment_year.split("-", 1)[0])
    except (ValueError, IndexError):
        return None
    return f"{first_year - 1}-{str(first_year)[-2:]}"


def is_yes(value: str | None) -> bool:
    return value == "yes"


def money(value: Any | None) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def value_at_path(profile: CanonicalTaxProfile, path: str) -> Any | None:
    value: Any = profile
    for part in path.split("."):
        if hasattr(value, part):
            value = getattr(value, part)
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def values_match(left: Any, right: Any) -> bool:
    try:
        return abs(float(left) - float(right)) <= 1
    except (TypeError, ValueError):
        return str(left).strip().upper() == str(right).strip().upper()


def mismatch_policy(path: str) -> tuple[str, ValidationSeverity, str]:
    if path == "user_identity.pan":
        return "identity.pan_mismatch", ValidationSeverity.CRITICAL, "PAN mismatch"
    if "tds" in path:
        return "reconciliation.tds_mismatch", ValidationSeverity.HIGH, "TDS does not match evidence"
    if path == "income_heads.salary.gross_amount":
        return "reconciliation.salary_mismatch", ValidationSeverity.HIGH, "Salary does not match evidence"
    if "interest" in path:
        return "reconciliation.interest_mismatch", ValidationSeverity.MEDIUM, "Interest income does not match evidence"
    return "reconciliation.evidence_conflict", ValidationSeverity.HIGH, "Evidence does not match profile"


def human_field(path: str) -> str:
    labels = {
        "user_identity.pan": "PAN",
        "income_heads.salary.gross_amount": "salary",
        "tax_payments.tds_salary": "salary TDS",
        "tax_payments.tds_other": "other TDS",
        "income_heads.other_sources.interest_savings_amount": "interest income",
    }
    return labels.get(path, path.replace("_", " ").replace(".", " "))

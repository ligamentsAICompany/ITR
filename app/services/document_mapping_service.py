"""Conservative v1 mappings from extracted document facts to intake fields."""

import hashlib
import re
from typing import Any

from app.models.document import ExtractedField, ExtractionSource


HEADER_MAPPINGS: dict[str, tuple[str, str, str, float]] = {
    "gross salary": ("Gross Salary", "salaryIncome", "income_heads.salary.gross_amount", 0.9),
    "salary": ("Gross Salary", "salaryIncome", "income_heads.salary.gross_amount", 0.82),
    "tds": ("TDS Salary", "tdsSalary", "tax_payments.tds_salary", 0.82),
    "tds salary": ("TDS Salary", "tdsSalary", "tax_payments.tds_salary", 0.9),
    "interest income": (
        "Interest Income",
        "otherSourcesInterest",
        "income_heads.other_sources.interest_savings_amount",
        0.76,
    ),
    "bank interest": (
        "Bank Interest",
        "otherSourcesInterest",
        "income_heads.other_sources.interest_savings_amount",
        0.76,
    ),
    "section 80c": ("Section 80C", "deduction80CAmount", "deductions.section_80c_amount", 0.86),
    "80c": ("Section 80C", "deduction80CAmount", "deductions.section_80c_amount", 0.82),
    "section 80d": ("Section 80D", "deduction80DAmount", "deductions.section_80d_amount", 0.86),
    "80d": ("Section 80D", "deduction80DAmount", "deductions.section_80d_amount", 0.82),
}

TEXT_PATTERNS: list[tuple[re.Pattern[str], tuple[str, str, str, float]]] = [
    (
        re.compile(r"gross\s+salary\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["gross salary"],
    ),
    (
        re.compile(r"tds\s*(?:salary)?\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["tds salary"],
    ),
    (
        re.compile(r"(?:bank\s+)?interest\s+income\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["interest income"],
    ),
]


class DocumentMappingService:
    def map_tabular_rows(self, document_id: str, rows: list[dict[str, Any]]) -> list[ExtractedField]:
        fields: list[ExtractedField] = []
        for row_index, row in enumerate(rows):
            for header, value in row.items():
                mapping = HEADER_MAPPINGS.get(_normalize_header(str(header)))
                normalized_value = _number_or_text(value)
                if mapping and normalized_value not in ("", None):
                    fields.append(_field(document_id, f"csv:{row_index}:{header}", mapping, normalized_value))
        return _dedupe_by_path(fields)

    def map_text(self, document_id: str, text: str) -> list[ExtractedField]:
        fields: list[ExtractedField] = []
        for pattern, mapping in TEXT_PATTERNS:
            match = pattern.search(text)
            if match:
                fields.append(_field(document_id, f"text:{pattern.pattern[:32]}", mapping, _parse_number(match.group(1))))
        return _dedupe_by_path(fields)


def _field(
    document_id: str,
    locator: str,
    mapping: tuple[str, str, str, float],
    value: str | int | float | bool,
) -> ExtractedField:
    label, raw_path, canonical_path, confidence = mapping
    return ExtractedField(
        field_id=f"{raw_path}:{hashlib.sha1(f'{document_id}:{locator}'.encode()).hexdigest()[:10]}",
        label=label,
        value=value,
        raw_path=raw_path,
        canonical_path=canonical_path,
        confidence=confidence,
        source=ExtractionSource(document_id=document_id, locator=locator),
    )


def _dedupe_by_path(fields: list[ExtractedField]) -> list[ExtractedField]:
    by_path: dict[str, ExtractedField] = {}
    for field in fields:
        by_path.setdefault(field.raw_path, field)
    return list(by_path.values())


def _normalize_header(header: str) -> str:
    return re.sub(r"\s+", " ", header.replace("_", " ")).strip().lower()


def _number_or_text(value: Any) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, int | float):
        return value
    return _parse_number(str(value).strip())


def _parse_number(value: str) -> str | int | float:
    cleaned = value.replace(",", "").strip()
    try:
        numeric = float(cleaned)
    except ValueError:
        return value.strip()
    return int(numeric) if numeric.is_integer() else numeric

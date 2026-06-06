"""Conservative v1 mappings from extracted document facts to intake fields."""

import hashlib
import re
from typing import Any

from app.models.document import ExtractedField, ExtractionSource


HEADER_MAPPINGS: dict[str, tuple[str, str, str, float]] = {
    "pan": ("PAN", "pan", "user_identity.pan", 0.82),
    "assessment year": ("Assessment Year", "assessmentYear", "assessment_year", 0.82),
    "ay": ("Assessment Year", "assessmentYear", "assessment_year", 0.76),
    "previous year": ("Previous Year", "previousYear", "previous_year", 0.82),
    "py": ("Previous Year", "previousYear", "previous_year", 0.76),
    "gross salary": ("Gross Salary", "salaryIncome", "income_heads.salary.gross_amount", 0.9),
    "salary": ("Gross Salary", "salaryIncome", "income_heads.salary.gross_amount", 0.82),
    "employer name": ("Employer Name", "employerName", "income_heads.salary.employer_name", 0.86),
    "employer": ("Employer Name", "employerName", "income_heads.salary.employer_name", 0.76),
    "employer tan": ("Employer TAN", "employerTan", "income_heads.salary.employer_tan", 0.72),
    "tan": ("Employer TAN", "employerTan", "income_heads.salary.employer_tan", 0.68),
    "tds": ("TDS Salary", "tdsSalary", "tax_payments.tds_salary", 0.82),
    "tds salary": ("TDS Salary", "tdsSalary", "tax_payments.tds_salary", 0.9),
    "salary tds": ("TDS Salary", "tdsSalary", "tax_payments.tds_salary", 0.9),
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
    "house property income": (
        "House Property Income",
        "housePropertyIncome",
        "income_heads.house_property.gross_amount",
        0.78,
    ),
    "house property annual value": (
        "House Property Annual Value",
        "housePropertyIncome",
        "income_heads.house_property.annual_value",
        0.78,
    ),
    "annual value": (
        "House Property Annual Value",
        "housePropertyIncome",
        "income_heads.house_property.annual_value",
        0.72,
    ),
    "house property interest": (
        "House Property Interest",
        "housePropertyInterest",
        "income_heads.house_property.interest_on_housing_loan",
        0.78,
    ),
    "interest on housing loan": (
        "House Property Interest",
        "housePropertyInterest",
        "income_heads.house_property.interest_on_housing_loan",
        0.78,
    ),
    "capital gains": ("Capital Gains", "capitalGainsIncome", "income_heads.capital_gains.gross_amount", 0.7),
    "stcg amount": ("STCG Amount", "stcgAmount", "income_heads.capital_gains.stcg_amount", 0.8),
    "short term capital gains": (
        "STCG Amount",
        "stcgAmount",
        "income_heads.capital_gains.stcg_amount",
        0.76,
    ),
    "ltcg 112a amount": (
        "LTCG 112A Amount",
        "ltcg112AAmount",
        "income_heads.capital_gains.ltcg_112a_amount",
        0.8,
    ),
    "112a amount": (
        "LTCG 112A Amount",
        "ltcg112AAmount",
        "income_heads.capital_gains.ltcg_112a_amount",
        0.76,
    ),
    "other ltcg amount": (
        "Other LTCG Amount",
        "otherLtcgAmount",
        "income_heads.capital_gains.other_ltcg_amount",
        0.78,
    ),
}

TEXT_PATTERNS: list[tuple[re.Pattern[str], tuple[str, str, str, float]]] = [
    (
        re.compile(r"gross\s+salary\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["gross salary"],
    ),
    (
        re.compile(r"\bpan\s*[:\-]?\s*([A-Z]{5}[0-9]{4}[A-Z])\b", re.I),
        HEADER_MAPPINGS["pan"],
    ),
    (
        re.compile(r"assessment\s+year\s*[:\-]?\s*(20\d{2}-\d{2})", re.I),
        HEADER_MAPPINGS["assessment year"],
    ),
    (
        re.compile(r"previous\s+year\s*[:\-]?\s*(20\d{2}-\d{2})", re.I),
        HEADER_MAPPINGS["previous year"],
    ),
    (
        re.compile(r"employer\s+name\s*[:\-]?\s*([^\n\r]+)", re.I),
        HEADER_MAPPINGS["employer name"],
    ),
    (
        re.compile(r"employer\s+tan\s*[:\-]?\s*([A-Z]{4}[0-9]{5}[A-Z])\b", re.I),
        HEADER_MAPPINGS["employer tan"],
    ),
    (
        re.compile(r"(?:salary\s+tds|tds\s*salary|tds)\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["tds salary"],
    ),
    (
        re.compile(r"(?:bank\s+)?interest\s+income\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["interest income"],
    ),
    (
        re.compile(r"(?:section\s+)?80c\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["80c"],
    ),
    (
        re.compile(r"(?:section\s+)?80d\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["80d"],
    ),
    (
        re.compile(r"house\s+property\s+income\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["house property income"],
    ),
    (
        re.compile(r"house\s+property\s+interest\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["house property interest"],
    ),
    (
        re.compile(r"stcg\s*(?:amount)?\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["stcg amount"],
    ),
    (
        re.compile(r"(?:ltcg\s+)?112a\s*(?:amount)?\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["ltcg 112a amount"],
    ),
    (
        re.compile(r"other\s+ltcg\s*(?:amount)?\s*[:\-]?\s*(?:inr|rs\.?)?\s*([0-9,]+(?:\.\d+)?)", re.I),
        HEADER_MAPPINGS["other ltcg amount"],
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

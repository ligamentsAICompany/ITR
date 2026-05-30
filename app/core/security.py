"""Security helpers for masking, sanitization, and validation."""

import re
from typing import Any

SENSITIVE_KEYS = {"pan", "aadhaar", "aadhaar_number", "aadhaar_last4"}
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
AADHAAR_RE = re.compile(r"\b[0-9]{12}\b")
DANGEROUS_PATTERNS = (
    re.compile(r"<\s*/?\s*script\b", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"\b(drop|alter|truncate)\s+(table|database)\b", re.IGNORECASE),
    re.compile(r"(--|;--|/\*|\*/|\bor\s+1\s*=\s*1\b)", re.IGNORECASE),
)


def mask_pan(value: str | None) -> str | None:
    if not value:
        return value
    normalized = str(value).strip().upper()
    if len(normalized) < 6:
        return "****"
    return f"{normalized[:5]}****{normalized[-1]}"


def mask_aadhaar(value: str | None) -> str | None:
    if not value:
        return value
    digits = re.sub(r"\D", "", str(value))
    if len(digits) < 4:
        return "****"
    return f"**** **** {digits[-4:]}"


def sanitize_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        if "loc" in value and "input" in value:
            return _sanitize_validation_error(value)
        sanitized = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered == "pan":
                sanitized[key] = mask_pan(str(item))
            elif lowered in {"aadhaar", "aadhaar_number"}:
                sanitized[key] = mask_aadhaar(str(item))
            elif lowered == "aadhaar_last4":
                sanitized[key] = "****"
            else:
                sanitized[key] = sanitize_for_log(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_log(item) for item in value]
    if isinstance(value, str):
        return _mask_sensitive_patterns(CONTROL_CHARS.sub("", value))
    return value


def _mask_sensitive_patterns(value: str) -> str:
    value = PAN_RE.sub(lambda match: mask_pan(match.group(0)) or "****", value)
    return AADHAAR_RE.sub(lambda match: mask_aadhaar(match.group(0)) or "****", value)


def _sanitize_validation_error(error: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(error)
    loc = sanitized.get("loc", [])
    field_name = str(loc[-1]).lower() if loc else ""
    if field_name == "pan":
        sanitized["input"] = mask_pan(str(sanitized.get("input")))
    elif field_name in {"aadhaar", "aadhaar_number"}:
        sanitized["input"] = mask_aadhaar(str(sanitized.get("input")))
    else:
        sanitized["input"] = sanitize_for_log(sanitized.get("input"))
    return sanitized


def assert_payload_safe(value: Any) -> None:
    if isinstance(value, dict):
        for item in value.values():
            assert_payload_safe(item)
        return
    if isinstance(value, list):
        for item in value:
            assert_payload_safe(item)
        return
    if isinstance(value, str):
        if CONTROL_CHARS.search(value):
            raise ValueError("Payload contains control characters")
        if any(pattern.search(value) for pattern in DANGEROUS_PATTERNS):
            raise ValueError("Payload contains unsafe content")

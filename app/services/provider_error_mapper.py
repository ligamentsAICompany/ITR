"""Map provider failures into safe internal errors."""

import json
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.validation import mask_sensitive


class ProviderErrorCode(StrEnum):
    AUTH_FAILED = "AUTH_FAILED"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    SCHEMA_REJECTED = "SCHEMA_REJECTED"
    SUBMISSION_DUPLICATE = "SUBMISSION_DUPLICATE"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    STATUS_UNKNOWN = "STATUS_UNKNOWN"
    EVERIFICATION_FAILED = "EVERIFICATION_FAILED"
    ACK_NOT_AVAILABLE = "ACK_NOT_AVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class ProviderErrorSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProviderMappedError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ProviderErrorCode
    safe_message: str
    retryable: bool
    severity: ProviderErrorSeverity
    audit_message: str

    @field_validator("safe_message", "audit_message")
    @classmethod
    def sanitize_text(cls, value: str) -> str:
        return sanitize_provider_text(value)


def map_provider_error(error: Any, *, operation: str) -> ProviderMappedError:
    text = sanitize_provider_text(error)
    lowered = text.lower()
    if any(item in lowered for item in ("401", "403", "auth", "credential", "unauthorized")):
        return ProviderMappedError(
            code=ProviderErrorCode.AUTH_FAILED,
            safe_message="Provider authentication failed. Please check secure provider configuration.",
            retryable=False,
            severity=ProviderErrorSeverity.CRITICAL,
            audit_message=f"{operation}: {text}",
        )
    if "duplicate" in lowered:
        return ProviderMappedError(
            code=ProviderErrorCode.SUBMISSION_DUPLICATE,
            safe_message="Provider reported this submission may already exist.",
            retryable=False,
            severity=ProviderErrorSeverity.WARNING,
            audit_message=f"{operation}: {text}",
        )
    if "rate" in lowered or "429" in lowered:
        return ProviderMappedError(
            code=ProviderErrorCode.RATE_LIMITED,
            safe_message="Provider rate limit reached. Please retry after the provider interval.",
            retryable=True,
            severity=ProviderErrorSeverity.WARNING,
            audit_message=f"{operation}: {text}",
        )
    if "timeout" in lowered or "timed out" in lowered:
        return ProviderMappedError(
            code=ProviderErrorCode.TIMEOUT,
            safe_message="Provider request timed out. Please retry later.",
            retryable=True,
            severity=ProviderErrorSeverity.WARNING,
            audit_message=f"{operation}: {text}",
        )
    if "schema" in lowered:
        return ProviderMappedError(
            code=ProviderErrorCode.SCHEMA_REJECTED,
            safe_message="Provider rejected the export schema. Please review validation results.",
            retryable=False,
            severity=ProviderErrorSeverity.ERROR,
            audit_message=f"{operation}: {text}",
        )
    if "payload" in lowered or "invalid" in lowered:
        return ProviderMappedError(
            code=ProviderErrorCode.INVALID_PAYLOAD,
            safe_message="Provider rejected the export payload. Please review filing readiness.",
            retryable=False,
            severity=ProviderErrorSeverity.ERROR,
            audit_message=f"{operation}: {text}",
        )
    if "ack" in lowered or operation == "get_acknowledgement":
        return ProviderMappedError(
            code=ProviderErrorCode.ACK_NOT_AVAILABLE,
            safe_message="Provider acknowledgement is not available yet.",
            retryable=True,
            severity=ProviderErrorSeverity.INFO,
            audit_message=f"{operation}: {text}",
        )
    if "everification" in lowered or operation.startswith("everification"):
        return ProviderMappedError(
            code=ProviderErrorCode.EVERIFICATION_FAILED,
            safe_message="Provider e-verification is not available for this submission.",
            retryable=False,
            severity=ProviderErrorSeverity.WARNING,
            audit_message=f"{operation}: {text}",
        )
    if "status" in lowered:
        return ProviderMappedError(
            code=ProviderErrorCode.STATUS_UNKNOWN,
            safe_message="Provider status is unknown. Please retry later.",
            retryable=True,
            severity=ProviderErrorSeverity.WARNING,
            audit_message=f"{operation}: {text}",
        )
    return ProviderMappedError(
        code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
        safe_message="Provider is unavailable. Please retry later.",
        retryable=True,
        severity=ProviderErrorSeverity.ERROR,
        audit_message=f"{operation}: {text}",
    )


def sanitize_provider_text(value: Any) -> str:
    if not isinstance(value, str):
        try:
            value = json.dumps(value, sort_keys=True, default=str)
        except TypeError:
            value = str(value)
    text = str(mask_sensitive(value))
    text = re.sub(
        r"(?i)([\"']?(?:client_secret|token|access_token|refresh_token|authorization|api_key)[\"']?\s*[:=]\s*)[\"']?[^,\s\"'}]+[\"']?",
        r"\1[redacted]",
        text,
    )
    text = re.sub(r"(?i)(bearer)\s+[a-z0-9._\-]+", r"\1 [redacted]", text)
    return text

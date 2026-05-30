"""Retry, timeout, and backoff policy for provider operations."""

import time
from collections.abc import Callable
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.services.provider_error_mapper import map_provider_error

T = TypeVar("T")


class ProviderRetryResult(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    value: T | None = None
    attempts: int
    retry_count: int
    error_code: str | None = None
    safe_message: str | None = None
    retryable: bool = False
    audit_events: list[dict[str, str | int]] = Field(default_factory=list)


class ProviderRetryPolicy:
    def __init__(self, *, retry_count: int | None = None, backoff_seconds: float | None = None, timeout_seconds: int | None = None) -> None:
        settings = get_settings()
        self.retry_count = settings.eri_retry_count if retry_count is None else retry_count
        self.backoff_seconds = getattr(settings, "eri_retry_backoff_seconds", 1.0) if backoff_seconds is None else backoff_seconds
        self.timeout_seconds = settings.eri_timeout_seconds if timeout_seconds is None else timeout_seconds

    def run(self, func: Callable[[], T], *, operation_name: str | None = None, operation: str | None = None) -> ProviderRetryResult[T]:
        operation_label = operation_name or operation or "provider_operation"
        attempts = 0
        audit_events: list[dict[str, str | int]] = []
        while True:
            attempts += 1
            try:
                return ProviderRetryResult(value=func(), attempts=attempts, retry_count=attempts - 1, audit_events=audit_events)
            except Exception as exc:  # noqa: BLE001 - policy must map arbitrary provider failures safely.
                mapped = map_provider_error(exc, operation=operation_label)
                if not mapped.retryable or attempts > self.retry_count:
                    return ProviderRetryResult(
                        attempts=attempts,
                        retry_count=attempts - 1,
                        error_code=mapped.code.value,
                        safe_message=mapped.safe_message,
                        retryable=mapped.retryable,
                        audit_events=audit_events,
                    )
                audit_events.append({"operation": operation_label, "attempt": attempts, "error_code": mapped.code.value})
                if self.backoff_seconds > 0:
                    time.sleep(self.backoff_seconds * (2 ** (attempts - 1)))

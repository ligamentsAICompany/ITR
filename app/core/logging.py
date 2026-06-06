"""Logging setup and request/response logging middleware."""

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter for API events."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
        }
        for key in (
            "event",
            "request_id",
            "trace_id",
            "method",
            "path",
            "status_code",
            "elapsed_ms",
            "reason",
            "role",
            "organization_id",
            "resource_type",
            "resource_id",
            "counter",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


async def request_response_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    logger = logging.getLogger("itr_api")
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    request.state.trace_id = trace_id
    log_context = {
        "request_id": request_id,
        "trace_id": trace_id,
        "method": request.method,
        "path": request.url.path,
    }
    logger.info("request started", extra={"event": "request_start", **log_context})
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request failed", extra={"event": "request_error", **log_context})
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Trace-ID"] = trace_id
    logger.info(
        "request completed",
        extra={
            "event": "request_end",
            "status_code": response.status_code,
            "elapsed_ms": round(elapsed_ms, 2),
            **log_context,
        },
    )
    return response

"""Central API error handlers."""

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.security import sanitize_for_log

logger = logging.getLogger("itr_api")


class InvalidSchemaError(Exception):
    """Validation error raised after request parsing but before model validation."""

    def __init__(self, details: list[dict[str, Any]]) -> None:
        self.details = details
        super().__init__("invalid schema")


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.warning(
        "invalid schema",
        extra={
            "event": "invalid_schema",
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
            "method": request.method,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_schema", "details": sanitize_for_log(exc.errors())},
    )


async def invalid_schema_exception_handler(
    request: Request,
    exc: InvalidSchemaError,
) -> JSONResponse:
    logger.warning(
        "invalid schema",
        extra={
            "event": "invalid_schema",
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
            "method": request.method,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_schema", "details": sanitize_for_log(exc.details)},
    )


async def pydantic_validation_exception_handler(
    request: Request,
    exc: ValidationError,
) -> JSONResponse:
    logger.warning(
        "invalid schema",
        extra={
            "event": "invalid_schema",
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
            "method": request.method,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_schema", "details": sanitize_for_log(exc.errors())},
    )


async def internal_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "internal error",
        extra={
            "event": "internal_error",
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
            "method": request.method,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "Internal server error"},
    )

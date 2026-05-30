"""FastAPI entrypoint for the deterministic ITR classification backend."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import (
    InvalidSchemaError,
    internal_exception_handler,
    invalid_schema_exception_handler,
    pydantic_validation_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging, request_response_logging_middleware
from app.core.rate_limit import rate_limit_middleware
from app.core.request_validation import request_validation_middleware

configure_logging()
settings = get_settings()
settings.validate_startup()

app = FastAPI(
    title="Deterministic ITR Classification API",
    version="0.1.0",
    debug=settings.debug,
)

app.middleware("http")(rate_limit_middleware)
app.middleware("http")(request_validation_middleware)
app.middleware("http")(request_response_logging_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(InvalidSchemaError, invalid_schema_exception_handler)
app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
app.add_exception_handler(Exception, internal_exception_handler)
app.include_router(router, prefix="/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return _health_payload(api_version="v1")


@app.get("/v1/health")
def versioned_health() -> dict[str, str]:
    return _health_payload(api_version="v1")


def _health_payload(*, api_version: str) -> dict[str, str]:
    current = get_settings()
    return {
        "status": "ok",
        "api_version": api_version,
        "environment": current.environment,
        "persistence_backend": current.persistence_backend,
        "storage_backend": current.storage_backend,
        "auth_mode": current.auth_mode,
    }

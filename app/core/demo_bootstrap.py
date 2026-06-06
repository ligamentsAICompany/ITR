"""Demo runtime bootstrap for Cloud Run-safe local persistence."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.database import init_database
from app.tools.load_demo_schema_packs import load_demo_schema_packs

logger = logging.getLogger(__name__)


def bootstrap_demo_runtime() -> dict[str, Any]:
    """Initialize demo-only runtime dependencies without secrets or external services."""

    settings = get_settings()
    summary: dict[str, Any] = {
        "environment": settings.environment,
        "persistence_backend": settings.persistence_backend,
        "storage_backend": settings.storage_backend,
        "provider_mode": settings.filing_provider_mode,
        "live_filing_enabled": settings.allow_live_filing,
        "sqlite_initialized": False,
        "local_storage_ready": False,
        "schema_packs_loaded": 0,
    }
    if settings.environment != "demo":
        logger.info(
            "Demo bootstrap skipped for non-demo runtime",
            extra={"environment": settings.environment, "schema_packs_loaded": 0},
        )
        return summary

    try:
        if settings.persistence_backend != "memory":
            init_database()
            summary["sqlite_initialized"] = settings.persistence_backend == "sqlite"

        if settings.storage_backend == "local":
            Path(settings.document_storage_dir).mkdir(parents=True, exist_ok=True)
            summary["local_storage_ready"] = True

        if settings.auto_load_demo_schema_packs:
            summary["schema_packs_loaded"] = len(load_demo_schema_packs())

        logger.info("Demo runtime bootstrap complete", extra=summary)
        return summary
    except Exception:
        logger.exception(
            "Demo runtime bootstrap failed",
            extra={
                "environment": settings.environment,
                "persistence_backend": settings.persistence_backend,
                "storage_backend": settings.storage_backend,
                "provider_mode": settings.filing_provider_mode,
                "live_filing_enabled": settings.allow_live_filing,
            },
        )
        raise RuntimeError("Demo runtime bootstrap failed; check safe startup logs for subsystem status") from None

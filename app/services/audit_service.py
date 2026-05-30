"""Best-effort audit trail writer with strict-mode option."""

import hashlib
import logging
from typing import Any

from fastapi import Request

from app.core.config import get_settings
from app.models.audit import AuditEvent
from app.models.auth import SessionContext
from app.repositories.audit_repository import AuditRepository

logger = logging.getLogger("itr_audit")


class AuditService:
    def __init__(self, repository: AuditRepository | None = None) -> None:
        self.repository = repository or AuditRepository()

    def record(
        self,
        *,
        event_type: str,
        session: SessionContext,
        resource_type: str,
        resource_id: str,
        request: Request | None = None,
        metadata_summary: dict[str, Any] | None = None,
    ) -> None:
        try:
            event = AuditEvent(
                event_type=event_type,
                actor_user_id=session.user_id,
                organization_id=session.organization_id,
                resource_type=resource_type,
                resource_id=resource_id,
                request_id=session.request_id,
                ip_hash=_ip_hash(request),
                client_context=request.headers.get("user-agent")[:120] if request else None,
                metadata_summary=metadata_summary or {},
            )
            self.repository.save(event)
            logger.info(
                "audit event recorded",
                extra={
                    "event": event.event_type,
                    "request_id": event.request_id,
                    "resource_type": event.resource_type,
                    "resource_id": event.resource_id,
                    "organization_id": event.organization_id,
                    "counter": _counter_for(event.event_type),
                },
            )
        except Exception:
            if get_settings().audit_strict:
                raise


def _ip_hash(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return hashlib.sha256(request.client.host.encode("utf-8")).hexdigest()


def _counter_for(event_type: str) -> str:
    counters = {
        "access_denied": "access_denied",
        "document_extracted": "extraction_events",
        "validation_run": "validation_runs",
        "tax_computation": "tax_computations",
        "filing_package_generated": "package_generation",
    }
    return counters.get(event_type, "audit_events")

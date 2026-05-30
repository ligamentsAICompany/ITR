"""Best-effort audit trail writer with strict-mode option."""

import hashlib
from typing import Any

from fastapi import Request

from app.core.config import get_settings
from app.models.audit import AuditEvent
from app.models.auth import SessionContext
from app.repositories.audit_repository import AuditRepository


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
        except Exception:
            if get_settings().audit_strict:
                raise


def _ip_hash(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return hashlib.sha256(request.client.host.encode("utf-8")).hexdigest()

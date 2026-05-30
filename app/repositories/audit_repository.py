"""Repository for privacy-safe audit events."""

from app.core.database import get_json_record, save_json_record
from app.models.audit import AuditEvent

AUDIT_EVENT_CACHE: dict[str, AuditEvent] = {}


class AuditRepository:
    table_name = "audit_events"

    def save(self, event: AuditEvent) -> AuditEvent:
        AUDIT_EVENT_CACHE[event.event_id] = event
        save_json_record(
            self.table_name,
            event.event_id,
            event.model_dump(mode="json"),
            event.timestamp.isoformat(),
            event.timestamp.isoformat(),
        )
        return event

    def get(self, event_id: str) -> AuditEvent | None:
        cached = AUDIT_EVENT_CACHE.get(event_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table_name, event_id)
        if payload is None:
            return None
        event = AuditEvent.model_validate(payload)
        AUDIT_EVENT_CACHE[event.event_id] = event
        return event

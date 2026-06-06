"""Persistence for uploaded official schema packs."""

from app.core.database import get_json_record, list_json_records, save_json_record
from app.models.schema_pack import SchemaPack, SchemaPackStatus

SCHEMA_PACK_CACHE: dict[str, SchemaPack] = {}
SCHEMA_PACK_CONTENT_CACHE: dict[str, dict] = {}


class SchemaPackRepository:
    table = "schema_packs"
    content_table = "schema_pack_contents"

    def save(self, schema_pack: SchemaPack, content: dict | None = None) -> SchemaPack:
        SCHEMA_PACK_CACHE[schema_pack.schema_pack_id] = schema_pack
        save_json_record(
            self.table,
            schema_pack.schema_pack_id,
            schema_pack.model_dump(mode="json"),
            schema_pack.uploaded_at.isoformat(),
            schema_pack.uploaded_at.isoformat(),
        )
        if content is not None:
            SCHEMA_PACK_CONTENT_CACHE[schema_pack.schema_pack_id] = content
            save_json_record(
                self.content_table,
                schema_pack.schema_pack_id,
                {"schema_pack_id": schema_pack.schema_pack_id, "content": content},
                schema_pack.uploaded_at.isoformat(),
                schema_pack.uploaded_at.isoformat(),
            )
        return schema_pack

    def get(self, schema_pack_id: str) -> SchemaPack | None:
        cached = SCHEMA_PACK_CACHE.get(schema_pack_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table, schema_pack_id)
        if payload is None:
            return None
        schema_pack = SchemaPack.model_validate(payload)
        SCHEMA_PACK_CACHE[schema_pack.schema_pack_id] = schema_pack
        return schema_pack

    def get_content(self, schema_pack_id: str) -> dict | None:
        cached = SCHEMA_PACK_CONTENT_CACHE.get(schema_pack_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.content_table, schema_pack_id)
        if payload is None:
            return None
        content = dict(payload["content"])
        SCHEMA_PACK_CONTENT_CACHE[schema_pack_id] = content
        return content

    def list(self) -> list[SchemaPack]:
        for payload in list_json_records(self.table):
            schema_pack = SchemaPack.model_validate(payload)
            SCHEMA_PACK_CACHE.setdefault(schema_pack.schema_pack_id, schema_pack)
        return sorted(SCHEMA_PACK_CACHE.values(), key=lambda item: item.uploaded_at)

    def active_for(self, *, assessment_year: str, itr_form: str) -> SchemaPack | None:
        for schema_pack in self.list():
            if schema_pack.assessment_year == assessment_year and schema_pack.itr_form == itr_form and schema_pack.is_active:
                return schema_pack
        return None

    def activate(self, schema_pack_id: str) -> SchemaPack | None:
        target = self.get(schema_pack_id)
        if target is None:
            return None
        for schema_pack in self.list():
            if schema_pack.assessment_year == target.assessment_year and schema_pack.itr_form == target.itr_form:
                updated = schema_pack.model_copy(update={"is_active": False, "status": SchemaPackStatus.ACCEPTED})
                self.save(updated)
        active = target.model_copy(update={"is_active": True, "status": SchemaPackStatus.ACTIVE})
        self.save(active)
        return active

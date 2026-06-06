"""Import and activate versioned official schema packs."""

import hashlib
import json
import zipfile
from io import BytesIO
from typing import Any

from jsonschema import Draft202012Validator, exceptions

from app.models.filing_package import safe_filename
from app.models.schema_pack import SchemaPack
from app.repositories.schema_pack_repository import SchemaPackRepository

MAX_SCHEMA_PACK_BYTES = 5 * 1024 * 1024
SUPPORTED_FORMS: set[str] = {"ITR-1", "ITR-2", "ITR-3", "ITR-4"}


class SchemaPackService:
    def __init__(self, repository: SchemaPackRepository | None = None) -> None:
        self.repository = repository or SchemaPackRepository()

    def upload(
        self,
        *,
        filename: str,
        content: bytes,
        assessment_year: str | None = None,
        previous_year: str | None = None,
        itr_form: str | None = None,
        schema_version: str | None = None,
    ) -> SchemaPack:
        if len(content) > MAX_SCHEMA_PACK_BYTES:
            raise ValueError("Schema pack is too large")
        source_filename, source_bytes, schema = self._read_schema(filename, content)
        Draft202012Validator.check_schema(schema)
        metadata = self._metadata(schema)
        resolved_itr_form = itr_form or metadata.get("itr_form")
        if resolved_itr_form not in SUPPORTED_FORMS:
            raise ValueError("Schema pack must declare supported ITR form ITR-1 through ITR-4")
        resolved_assessment_year = assessment_year or metadata.get("assessment_year")
        resolved_schema_version = schema_version or metadata.get("schema_version") or schema.get("$id") or "unknown"
        if not resolved_assessment_year:
            raise ValueError("Schema pack must declare assessment year")
        schema_pack = SchemaPack(
            assessment_year=str(resolved_assessment_year),
            previous_year=previous_year or metadata.get("previous_year"),
            itr_form=resolved_itr_form,  # type: ignore[arg-type]
            schema_version=str(resolved_schema_version),
            source_filename=source_filename,
            source_hash=hashlib.sha256(source_bytes).hexdigest(),
            is_active=False,
        )
        return self.repository.save(schema_pack, schema)

    def list(self) -> list[SchemaPack]:
        return self.repository.list()

    def get(self, schema_pack_id: str) -> SchemaPack | None:
        return self.repository.get(schema_pack_id)

    def activate(self, schema_pack_id: str) -> SchemaPack | None:
        schema_pack = self.repository.get(schema_pack_id)
        if schema_pack is None:
            return None
        if self.repository.get_content(schema_pack_id) is None:
            raise ValueError("Schema pack content is unavailable")
        return self.repository.activate(schema_pack_id)

    def active_for(self, *, assessment_year: str, itr_form: str) -> tuple[SchemaPack, dict] | None:
        schema_pack = self.repository.active_for(assessment_year=assessment_year, itr_form=itr_form)
        if schema_pack is None:
            return None
        content = self.repository.get_content(schema_pack.schema_pack_id)
        if content is None:
            return None
        return schema_pack, content

    def _read_schema(self, filename: str, content: bytes) -> tuple[str, bytes, dict[str, Any]]:
        safe = safe_filename(filename)
        lowered = safe.lower()
        if lowered.endswith(".json"):
            return safe, content, self._parse_json(content)
        if not lowered.endswith(".zip"):
            raise ValueError("Only .json schema files and .zip files containing JSON are supported")
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                json_names = [name for name in archive.namelist() if safe_filename(name).lower().endswith(".json")]
                if len(json_names) != 1:
                    raise ValueError("ZIP schema pack must contain exactly one JSON schema file")
                nested_name = safe_filename(json_names[0])
                nested_content = archive.read(json_names[0])
        except zipfile.BadZipFile as exc:
            raise ValueError("Invalid ZIP schema pack") from exc
        return nested_name, nested_content, self._parse_json(nested_content)

    def _parse_json(self, content: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON schema pack") from exc
        if not isinstance(payload, dict):
            raise ValueError("Schema pack JSON must be an object")
        try:
            Draft202012Validator.check_schema(payload)
        except exceptions.SchemaError as exc:
            raise ValueError("Invalid JSON Schema") from exc
        return payload

    def _metadata(self, schema: dict[str, Any]) -> dict[str, Any]:
        raw = schema.get("x-itr") or schema.get("x_itr") or {}
        return raw if isinstance(raw, dict) else {}

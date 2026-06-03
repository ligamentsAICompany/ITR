"""Load synthetic demo schema packs for the AY 2026-27 demo workflow."""

import argparse
import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.core.database import get_json_record, list_json_records
from app.models.schema_pack import SchemaPack
from app.services.schema_pack_service import SchemaPackService

DEMO_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "demo_data" / "schema_packs"
ASSESSMENT_YEAR = "2026-27"
PREVIOUS_YEAR = "2025-26"
PRODUCTION_ENV_NAMES = {"prod", "production"}


@dataclass(frozen=True)
class DemoSchemaPackSpec:
    itr_form: str
    filename: str


DEMO_SCHEMA_PACKS: tuple[DemoSchemaPackSpec, ...] = (
    DemoSchemaPackSpec("ITR-1", "itr1_ay2026_27_test_schema.json"),
    DemoSchemaPackSpec("ITR-2", "itr2_ay2026_27_test_schema.json"),
    DemoSchemaPackSpec("ITR-3", "itr3_ay2026_27_test_schema.json"),
    DemoSchemaPackSpec("ITR-4", "itr4_ay2026_27_test_schema.json"),
)


def load_demo_schema_packs(
    *,
    schema_dir: Path = DEMO_SCHEMA_DIR,
    service: SchemaPackService | None = None,
) -> list[SchemaPack]:
    """Register and activate one synthetic demo schema pack per supported demo ITR."""

    schema_service = service or SchemaPackService()
    _hydrate_persisted_schema_packs(schema_service)
    activated: list[SchemaPack] = []

    for spec in DEMO_SCHEMA_PACKS:
        path = schema_dir / spec.filename
        content = path.read_bytes()
        schema = json.loads(content.decode("utf-8"))
        _validate_demo_schema_metadata(schema, spec)
        source_hash = hashlib.sha256(content).hexdigest()
        schema_version = str(schema["x-itr"]["schema_version"])
        existing = _find_existing_pack(
            schema_service,
            itr_form=spec.itr_form,
            source_hash=source_hash,
            schema_version=schema_version,
        )
        pack = existing or schema_service.upload(
            filename=spec.filename,
            content=content,
            assessment_year=ASSESSMENT_YEAR,
            previous_year=PREVIOUS_YEAR,
            itr_form=spec.itr_form,
            schema_version=schema_version,
        )
        active = schema_service.activate(pack.schema_pack_id)
        if active is None:
            raise RuntimeError(f"Could not activate demo schema pack for {spec.itr_form}")
        activated.append(active)

    return activated


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load synthetic demo ITR schema packs.")
    parser.add_argument(
        "--allow-production-demo",
        action="store_true",
        help="Explicitly allow loading in production-like environments. Intended only for controlled demo deployments.",
    )
    args = parser.parse_args(argv)
    if _is_production() and not args.allow_production_demo:
        print("Refusing to load demo schema packs in production without --allow-production-demo.")
        return 2

    activated = load_demo_schema_packs()
    summary = {
        "summary": "Synthetic demo schema packs loaded",
        "assessment_year": ASSESSMENT_YEAR,
        "schema_packs": [
            {
                "itr_form": item.itr_form,
                "assessment_year": item.assessment_year,
                "schema_pack_id": item.schema_pack_id,
                "schema_version": item.schema_version,
                "active": item.is_active,
            }
            for item in activated
        ],
        "notice": "Synthetic test schema pack only. Not official government schema. For demo validation only.",
        "secrets_required": False,
        "live_filing_enabled": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _hydrate_persisted_schema_packs(service: SchemaPackService) -> None:
    """Load persisted packs into the repository cache so activation can deactivate siblings."""

    for payload in list_json_records(service.repository.table):
        schema_pack = SchemaPack.model_validate(payload)
        if service.repository.get(schema_pack.schema_pack_id) is not None:
            continue
        content_record = get_json_record(service.repository.content_table, schema_pack.schema_pack_id)
        content = content_record.get("content") if isinstance(content_record, dict) else None
        service.repository.save(schema_pack, content if isinstance(content, dict) else None)


def _find_existing_pack(
    service: SchemaPackService,
    *,
    itr_form: str,
    source_hash: str,
    schema_version: str,
) -> SchemaPack | None:
    for pack in service.list():
        if (
            pack.assessment_year == ASSESSMENT_YEAR
            and pack.itr_form == itr_form
            and pack.schema_version == schema_version
            and pack.source_hash == source_hash
            and service.repository.get_content(pack.schema_pack_id) is not None
        ):
            return pack
    return None


def _validate_demo_schema_metadata(schema: dict, spec: DemoSchemaPackSpec) -> None:
    metadata = schema.get("x-itr")
    if not isinstance(metadata, dict):
        raise ValueError(f"{spec.filename} is missing x-itr metadata")
    if metadata.get("assessment_year") != ASSESSMENT_YEAR or metadata.get("itr_form") != spec.itr_form:
        raise ValueError(f"{spec.filename} metadata does not match {spec.itr_form} {ASSESSMENT_YEAR}")
    disclaimer = str(metadata.get("disclaimer", "")).lower()
    if "synthetic test schema pack only" not in disclaimer or "not official government schema" not in disclaimer:
        raise ValueError(f"{spec.filename} must clearly disclaim official schema status")


def _is_production() -> bool:
    return (
        os.getenv("APP_ENV", "").strip().lower() in PRODUCTION_ENV_NAMES
        or os.getenv("ENVIRONMENT", "").strip().lower() in PRODUCTION_ENV_NAMES
    )


if __name__ == "__main__":
    raise SystemExit(main())

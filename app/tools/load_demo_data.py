"""Inspect Phase 13 synthetic demo data without seeding production records."""

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any


DEMO_ROOT = Path(__file__).resolve().parents[2] / "demo_data"
PRODUCTION_ENV_NAMES = {"prod", "production"}
SENSITIVE_KEYS = {"pan", "aadhaar", "aadhaar_last4"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize synthetic pilot demo data safely.")
    parser.add_argument("--demo", action="store_true", help="Required acknowledgement that only fake demo data is used.")
    parser.add_argument(
        "--allow-production-demo",
        action="store_true",
        help="Explicitly allow summary mode when APP_ENV/ENVIRONMENT is production. Does not write data.",
    )
    return parser


def _is_production() -> bool:
    return (
        os.getenv("APP_ENV", "").strip().lower() in PRODUCTION_ENV_NAMES
        or os.getenv("ENVIRONMENT", "").strip().lower() in PRODUCTION_ENV_NAMES
    )


def _read_json_files(folder: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["_file_stem"] = path.stem
        records.append(payload)
    return records


def _safe_persona_summary(persona: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": persona.get("id") or persona.get("_file_stem"),
        "scenario": persona.get("scenario"),
        "candidate_itr": persona.get("candidate_itr"),
        "documents": persona.get("documents", []),
        "live_filing_enabled": persona.get("live_filing_enabled"),
        "data_classification": persona.get("data_classification"),
    }


def _contains_sensitive_keys(payload: Any) -> bool:
    if isinstance(payload, dict):
        return any(key in SENSITIVE_KEYS or _contains_sensitive_keys(value) for key, value in payload.items())
    if isinstance(payload, list):
        return any(_contains_sensitive_keys(value) for value in payload)
    return False


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.demo:
        print("Refusing to inspect demo data without explicit --demo acknowledgement.")
        return 2
    if _is_production() and not args.allow_production_demo:
        print("Refusing production demo summary without --allow-production-demo. No data was written.")
        return 2

    personas = _read_json_files(DEMO_ROOT / "personas")
    expected_outputs = _read_json_files(DEMO_ROOT / "expected_outputs")
    unsafe_expected = [item.get("_file_stem", "unknown") for item in expected_outputs if _contains_sensitive_keys(item)]
    if unsafe_expected:
        print(f"Unsafe expected-output keys found: {', '.join(unsafe_expected)}")
        return 2

    summary = {
        "summary": "Synthetic demo personas",
        "mode": "summary_only_no_database_writes",
        "synthetic_demo_personas": [_safe_persona_summary(persona) for persona in personas],
        "expected_outputs": [item.get("_file_stem") for item in expected_outputs],
        "notice": "Synthetic demo data only. Live government filing remains disabled.",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

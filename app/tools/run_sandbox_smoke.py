"""Run a controlled sandbox smoke flow with test-only data."""

import json
from collections.abc import Sequence

from app.services.sandbox_smoke_service import SandboxSmokeService


def main(argv: Sequence[str] | None = None) -> int:
    _ = argv
    result = SandboxSmokeService().run()
    payload = result.model_dump(mode="json")
    payload["safe_summary"] = "Sandbox smoke used test-only payloads and did not print raw provider payloads or secrets."
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if result.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

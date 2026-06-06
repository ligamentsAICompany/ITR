"""Generate a safe client pilot readiness report."""

import json
from collections.abc import Sequence

from app.services.pilot_readiness_service import PilotReadinessService


def main(argv: Sequence[str] | None = None) -> int:
    _ = argv
    report = PilotReadinessService().generate()
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

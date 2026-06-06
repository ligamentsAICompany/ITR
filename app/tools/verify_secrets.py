"""Verify sandbox secret accessibility without printing secret values."""

import json
from collections.abc import Sequence

from app.services.secret_verification_service import SecretVerificationService


def main(argv: Sequence[str] | None = None) -> int:
    _ = argv
    report = SecretVerificationService().verify_sandbox()
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0 if report.verified else 1


if __name__ == "__main__":
    raise SystemExit(main())

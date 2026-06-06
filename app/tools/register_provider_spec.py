"""Register an approved non-secret sandbox provider spec."""

import argparse
import json
from collections.abc import Sequence

from app.services.provider_spec_registration_service import ProviderSpecRegistrationService


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args(argv)
    try:
        spec, spec_hash = ProviderSpecRegistrationService().register_file(args.file)
    except ValueError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "status": "registered",
                "provider_name": spec.provider_name,
                "provider_mode": spec.provider_mode.value,
                "spec_version": spec.spec_version,
                "active": spec.is_active,
                "sha256": spec_hash,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

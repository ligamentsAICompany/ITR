"""Run safe provider contract checks."""

import argparse
import json
from collections.abc import Sequence

from app.services.provider_contract_test_service import ProviderContractTestService


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="eri")
    parser.add_argument("--mode", default="sandbox")
    args = parser.parse_args(argv)
    result = ProviderContractTestService().run(provider=args.provider, mode=args.mode)
    payload = result.model_dump(mode="json")
    payload["safe_summary"] = "Provider contract tests completed without printing credentials or provider payloads."
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if result.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Repository for provider specs and contract-test results."""

from datetime import UTC, datetime

from app.core.database import get_json_record, list_json_records, save_json_record
from app.models.provider_integration import ProviderMode
from app.models.provider_spec import ProviderSpec

PROVIDER_SPEC_CACHE: dict[str, ProviderSpec] = {}
PROVIDER_CONTRACT_RESULT_CACHE: dict[str, dict] = {}


class ProviderSpecRepository:
    table = "provider_specs"

    def save(self, spec: ProviderSpec) -> ProviderSpec:
        if spec.is_active:
            for existing_id, existing in list(PROVIDER_SPEC_CACHE.items()):
                if (
                    existing.provider_name == spec.provider_name
                    and existing.provider_mode == spec.provider_mode
                    and existing.provider_spec_id != spec.provider_spec_id
                    and existing.is_active
                ):
                    deactivated = existing.model_copy(update={"is_active": False})
                    PROVIDER_SPEC_CACHE[existing_id] = deactivated
        PROVIDER_SPEC_CACHE[spec.provider_spec_id] = spec
        save_json_record(self.table, spec.provider_spec_id, spec.model_dump(mode="json"), spec.created_at.isoformat(), spec.created_at.isoformat())
        return spec

    def get(self, provider_spec_id: str) -> ProviderSpec | None:
        cached = PROVIDER_SPEC_CACHE.get(provider_spec_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table, provider_spec_id)
        if payload is None:
            return None
        spec = ProviderSpec.model_validate(payload)
        PROVIDER_SPEC_CACHE[spec.provider_spec_id] = spec
        return spec

    def get_active(self, *, provider_name: str, provider_mode: str | ProviderMode) -> ProviderSpec | None:
        mode = ProviderMode(provider_mode)
        cached = next(
            (
                spec
                for spec in PROVIDER_SPEC_CACHE.values()
                if spec.provider_name == provider_name and spec.provider_mode == mode and spec.is_active
            ),
            None,
        )
        if cached is not None:
            return cached
        for payload in list_json_records(self.table):
            spec = ProviderSpec.model_validate(payload)
            PROVIDER_SPEC_CACHE[spec.provider_spec_id] = spec
            if spec.provider_name == provider_name and spec.provider_mode == mode and spec.is_active:
                return spec
        return None


class ProviderContractResultRepository:
    table = "provider_contract_results"

    def save(self, *, provider: str, mode: str, result: dict) -> dict:
        key = f"{provider}:{mode}"
        PROVIDER_CONTRACT_RESULT_CACHE[key] = result
        timestamp = str(result.get("tested_at") or datetime.now(UTC).isoformat())
        save_json_record(self.table, key, result, timestamp, timestamp)
        return result

    def latest(self, *, provider: str, mode: str) -> dict | None:
        key = f"{provider}:{mode}"
        cached = PROVIDER_CONTRACT_RESULT_CACHE.get(key)
        if cached is not None:
            return cached
        persisted = get_json_record(self.table, key)
        if persisted is not None:
            PROVIDER_CONTRACT_RESULT_CACHE[key] = persisted
        return persisted

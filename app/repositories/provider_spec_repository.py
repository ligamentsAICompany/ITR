"""Repository for provider specs and contract-test results."""

from app.core.database import get_json_record, save_json_record
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
        return next(
            (
                spec
                for spec in PROVIDER_SPEC_CACHE.values()
                if spec.provider_name == provider_name and spec.provider_mode == mode and spec.is_active
            ),
            None,
        )


class ProviderContractResultRepository:
    def save(self, *, provider: str, mode: str, result: dict) -> dict:
        PROVIDER_CONTRACT_RESULT_CACHE[f"{provider}:{mode}"] = result
        return result

    def latest(self, *, provider: str, mode: str) -> dict | None:
        return PROVIDER_CONTRACT_RESULT_CACHE.get(f"{provider}:{mode}")

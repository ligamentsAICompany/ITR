"""Repository wrapper for deterministic tax computation results."""

from datetime import UTC, datetime

from app.core.database import get_json_record, save_json_record
from app.models.tax_computation import TaxComputationResult

TAX_COMPUTATION_CACHE: dict[str, TaxComputationResult] = {}


class TaxComputationRepository:
    table_name = "tax_computations"

    def save(self, result: TaxComputationResult) -> TaxComputationResult:
        TAX_COMPUTATION_CACHE[result.computation_id] = result
        now = datetime.now(UTC).isoformat()
        save_json_record(
            self.table_name,
            result.computation_id,
            result.model_dump(mode="json"),
            now,
            now,
        )
        return result

    def get(self, computation_id: str) -> TaxComputationResult | None:
        cached = TAX_COMPUTATION_CACHE.get(computation_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table_name, computation_id)
        if payload is None:
            return None
        result = TaxComputationResult.model_validate(payload)
        TAX_COMPUTATION_CACHE[computation_id] = result
        return result

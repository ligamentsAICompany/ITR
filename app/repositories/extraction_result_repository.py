"""Repository wrapper for document extraction results."""

from datetime import UTC, datetime

from app.core.database import get_json_record, save_json_record
from app.models.document import ExtractionResult

EXTRACTION_RESULT_CACHE: dict[str, ExtractionResult] = {}


class ExtractionResultRepository:
    table_name = "extraction_results"

    def save(self, result: ExtractionResult) -> ExtractionResult:
        EXTRACTION_RESULT_CACHE[result.document_id] = result
        now = datetime.now(UTC).isoformat()
        save_json_record(
            self.table_name,
            result.document_id,
            result.model_dump(mode="json"),
            result.created_at.isoformat(),
            now,
        )
        return result

    def get(self, document_id: str) -> ExtractionResult | None:
        cached = EXTRACTION_RESULT_CACHE.get(document_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table_name, document_id)
        if payload is None:
            return None
        result = ExtractionResult.model_validate(payload)
        EXTRACTION_RESULT_CACHE[document_id] = result
        return result

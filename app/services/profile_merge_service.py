"""Merge reviewed extraction fields into the raw intake payload."""

from typing import Any

from app.models.document import ExtractionResult, MergeExtractionResult


class ProfileMergeService:
    def merge(
        self,
        *,
        current_payload: dict[str, Any],
        extraction_result: ExtractionResult,
        approved_field_ids: list[str],
    ) -> MergeExtractionResult:
        approved = set(approved_field_ids)
        merged = dict(current_payload)
        applied: list[str] = []
        skipped: list[str] = []

        for field in extraction_result.fields:
            if field.field_id not in approved:
                skipped.append(field.field_id)
                continue
            merged[field.raw_path] = str(field.value)
            applied.append(field.field_id)

        return MergeExtractionResult(
            merged_payload=merged,
            applied_field_ids=applied,
            skipped_field_ids=skipped,
        )

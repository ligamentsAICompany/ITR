"""Repository wrapper for validation reports.

The module-level dictionary is retained as an MVP compatibility cache. SQLite is
the local development persistence backend; PostgreSQL can replace this class
behind the same save/get interface when DATABASE_URL points to a server backend.
"""

from datetime import UTC, datetime

from app.core.database import get_json_record, save_json_record
from app.models.validation import ValidationReport

VALIDATION_REPORT_CACHE: dict[str, ValidationReport] = {}


class ValidationReportRepository:
    table_name = "validation_reports"

    def save(self, report: ValidationReport) -> ValidationReport:
        VALIDATION_REPORT_CACHE[report.validation_run_id] = report
        now = datetime.now(UTC).isoformat()
        save_json_record(
            self.table_name,
            report.validation_run_id,
            report.model_dump(mode="json"),
            report.created_at.isoformat(),
            now,
        )
        return report

    def get(self, validation_run_id: str) -> ValidationReport | None:
        cached = VALIDATION_REPORT_CACHE.get(validation_run_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table_name, validation_run_id)
        if payload is None:
            return None
        report = ValidationReport.model_validate(payload)
        VALIDATION_REPORT_CACHE[validation_run_id] = report
        return report

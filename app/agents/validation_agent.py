"""Phase 2 validation agent constrained to deterministic validation outputs."""

from dataclasses import dataclass, field

from app.models.document import ExtractionResult, PublicDocumentMetadata
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationExplainResponse, ValidationReport
from app.services.validation_service import ValidationService


@dataclass
class ValidationAgentState:
    profile: CanonicalTaxProfile | None = None
    documents: list[PublicDocumentMetadata] = field(default_factory=list)
    extractions: list[ExtractionResult] = field(default_factory=list)
    validation_report: ValidationReport | None = None
    needs_review: bool = False
    readiness_score: int = 0
    execution_log: list[str] = field(default_factory=list)


class ValidationAgent:
    """Runs deterministic validation and explains only the resulting findings."""

    def __init__(self, validation_service: ValidationService | None = None) -> None:
        self.validation_service = validation_service or ValidationService()
        self.state = ValidationAgentState()

    def run(
        self,
        *,
        profile: CanonicalTaxProfile,
        documents: list[PublicDocumentMetadata],
        extractions: list[ExtractionResult],
        approved_field_ids: list[str],
        profile_id: str | None = None,
        session_id: str | None = None,
    ) -> ValidationReport:
        self.state.profile = profile
        self.state.documents = documents
        self.state.extractions = extractions
        self.state.execution_log.append("validation: deterministic rules started")
        report = self.validation_service.run(
            profile=profile,
            documents=documents,
            extractions=extractions,
            approved_field_ids=approved_field_ids,
            profile_id=profile_id,
            session_id=session_id,
        )
        self.state.validation_report = report
        self.state.needs_review = report.overall_status in {"failed", "needs_review", "warning"}
        self.state.readiness_score = report.readiness_score
        self.state.execution_log.append("validation: deterministic rules completed")
        return report

    def explain(self, report: ValidationReport) -> ValidationExplainResponse:
        if not report.issues:
            explanation = "Validation passed. No deterministic reconciliation issues were found."
            grounded_issue_ids: list[str] = []
        else:
            top_issues = sorted(report.issues, key=lambda issue: severity_rank(issue.severity))[:5]
            fragments = [
                f"{issue.title}: {issue.message} Suggested action: {issue.recommendation}"
                for issue in top_issues
            ]
            explanation = " ".join(fragments)
            grounded_issue_ids = [issue.issue_id for issue in top_issues]
        return ValidationExplainResponse(
            validation_run_id=report.validation_run_id,
            explanation=explanation,
            grounded_issue_ids=grounded_issue_ids,
        )


def severity_rank(severity: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(str(severity), 5)

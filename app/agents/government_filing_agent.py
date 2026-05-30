"""Read-only filing agent that explains deterministic filing state."""

from app.models.filing_submission import FilingExplanation
from app.repositories.filing_workflow_repository import FilingSubmissionRepository


class GovernmentFilingAgent:
    def __init__(self, *, submission_repository: FilingSubmissionRepository | None = None) -> None:
        self.submission_repository = submission_repository or FilingSubmissionRepository()

    def explain_submission(self, submission_id: str, session_user_id: str | None = None) -> FilingExplanation:
        submission = self.submission_repository.get(submission_id)
        if submission is None:
            return FilingExplanation(
                submission_id=submission_id,
                explanation="No filing submission exists for this request. Nothing has been submitted.",
                required_actions=["Create a filing submission draft after export generation."],
            )
        actions: list[str] = []
        if submission.submission_status in {"draft", "blocked"}:
            actions.append("Resolve readiness blockers, taxpayer consent, and reviewer approval before any submit action.")
        if submission.everification_status == "not_started" and submission.submission_status in {
            "submitted",
            "pending_verification",
        }:
            actions.append("Initiate e-verification only after provider-confirmed submission.")
        text = (
            f"Submission status is {submission.submission_status.replace('_', ' ')} in "
            f"{submission.provider_mode} provider mode. The agent cannot approve, submit, alter export payloads, "
            "or bypass consent and reviewer gates."
        )
        return FilingExplanation(submission_id=submission.submission_id, explanation=text, required_actions=actions)

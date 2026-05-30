"""Provider status polling foundation."""

from datetime import UTC, datetime

from app.models.audit import AuditEvent
from app.models.filing_submission import SubmissionStatus
from app.repositories.audit_repository import AuditRepository
from app.repositories.filing_workflow_repository import FilingSubmissionRepository
from app.services.filing_provider_factory import get_filing_provider, get_filing_provider_configuration


class ProviderStatusService:
    def __init__(
        self,
        *,
        submission_repository: FilingSubmissionRepository | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        self.submission_repository = submission_repository or FilingSubmissionRepository()
        self.audit_repository = audit_repository or AuditRepository()

    def poll_submission_status(self, *, submission_id: str):
        submission = self.submission_repository.get(submission_id)
        if submission is None:
            raise LookupError("Filing submission not found")
        if not submission.provider_reference_id:
            raise ValueError("Submission has no provider reference")
        config = get_filing_provider_configuration()
        if config.provider_mode == "live" and not config.live_allowed:
            raise ValueError("Live filing is disabled")
        provider = get_filing_provider()
        response = provider.get_submission_status(provider_reference_id=submission.provider_reference_id)
        if response.success:
            status = response.normalized_status or _normalize_status(response.status)
            submission.submission_status = status
        else:
            submission.failure_reason = response.safe_message or response.failure_reason or "Provider status check failed"
        submission.last_checked_at = datetime.now(UTC)
        submission.updated_at = datetime.now(UTC)
        saved = self.submission_repository.save(submission)
        self._audit(saved, response.status)
        return saved

    def _audit(self, submission, provider_status: str) -> None:
        actor = submission.created_by or submission.owner_user_id or "00000000-0000-4000-8000-000000000000"
        org = submission.organization_id or "00000000-0000-4000-8000-000000000000"
        self.audit_repository.save(
            AuditEvent(
                event_type="provider_status_checked",
                actor_user_id=actor,
                organization_id=org,
                resource_type="filing_submission",
                resource_id=submission.submission_id,
                request_id="provider-status-service",
                metadata_summary={
                    "provider": submission.provider,
                    "provider_mode": submission.provider_mode,
                    "provider_status": provider_status,
                    "submission_status": submission.submission_status,
                },
            )
        )


def _normalize_status(status: str) -> SubmissionStatus:
    status = status.lower()
    if status in {item.value for item in SubmissionStatus}:
        return SubmissionStatus(status)
    if status in {"acknowledgement_available", "available"}:
        return SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE
    if status in {"pending", "queued"}:
        return SubmissionStatus.PENDING_VERIFICATION
    if status in {"failed", "rejected"}:
        return SubmissionStatus.SUBMISSION_FAILED
    return SubmissionStatus.PENDING_VERIFICATION

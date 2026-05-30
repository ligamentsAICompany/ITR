"""Filing workflow service with consent, approval, and provider gates."""

from datetime import UTC, datetime, timedelta

from app.models.auth import SessionContext, UserRole
from app.models.filing_approval import ApprovalStatus, FilingApproval
from app.models.filing_consent import ConsentStatus, FilingConsent
from app.models.filing_submission import Acknowledgement, EVerificationStatus, FilingSubmission, SubmissionStatus
from app.repositories.filing_package_repository import FilingPackageRepository
from app.repositories.filing_workflow_repository import (
    AcknowledgementRepository,
    FilingApprovalRepository,
    FilingConsentRepository,
    FilingSubmissionRepository,
)
from app.repositories.itr_export_repository import ItrExportRepository
from app.services.authorization_service import AuthorizationService
from app.services.filing_provider_factory import get_filing_provider, get_filing_provider_configuration
from app.services.filing_readiness_service import FilingReadinessResult, FilingReadinessService


class FilingService:
    def __init__(
        self,
        *,
        package_repository: FilingPackageRepository | None = None,
        export_repository: ItrExportRepository | None = None,
        consent_repository: FilingConsentRepository | None = None,
        approval_repository: FilingApprovalRepository | None = None,
        submission_repository: FilingSubmissionRepository | None = None,
        acknowledgement_repository: AcknowledgementRepository | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        self.package_repository = package_repository or FilingPackageRepository()
        self.export_repository = export_repository or ItrExportRepository()
        self.consent_repository = consent_repository or FilingConsentRepository()
        self.approval_repository = approval_repository or FilingApprovalRepository()
        self.submission_repository = submission_repository or FilingSubmissionRepository()
        self.acknowledgement_repository = acknowledgement_repository or AcknowledgementRepository()
        self.authorization_service = authorization_service or AuthorizationService()
        self.readiness_service = FilingReadinessService(
            package_repository=self.package_repository,
            export_repository=self.export_repository,
            consent_repository=self.consent_repository,
            approval_repository=self.approval_repository,
            authorization_service=self.authorization_service,
        )

    def request_consent(self, *, package_id: str, export_id: str, consent_text: str, session: SessionContext, ip_hash: str | None = None, user_agent_hash: str | None = None) -> FilingConsent:
        package, export = self._package_export(package_id, export_id)
        self._require_access(session, package)
        self._require_access(session, export)
        consent = FilingConsent(
            user_id=package.owner_user_id or session.user_id,
            organization_id=package.organization_id or session.organization_id,
            package_id=package_id,
            export_id=export_id,
            consent_text=consent_text,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            ip_hash=ip_hash,
            user_agent_hash=user_agent_hash,
        )
        return self.consent_repository.save(consent)

    def grant_consent(self, *, consent_id: str, session: SessionContext) -> FilingConsent:
        consent = self._consent(consent_id)
        if session.role != UserRole.TAXPAYER or session.user_id != consent.user_id or session.organization_id != consent.organization_id:
            raise PermissionError("Only the taxpayer owner can grant filing consent")
        consent.consent_status = ConsentStatus.GRANTED
        consent.granted_at = datetime.now(UTC)
        return self.consent_repository.save(consent)

    def revoke_consent(self, *, consent_id: str, session: SessionContext) -> FilingConsent:
        consent = self._consent(consent_id)
        if session.user_id != consent.user_id or session.organization_id != consent.organization_id:
            raise PermissionError("Only the taxpayer owner can revoke filing consent")
        consent.consent_status = ConsentStatus.REVOKED
        consent.revoked_at = datetime.now(UTC)
        return self.consent_repository.save(consent)

    def request_approval(self, *, package_id: str, export_id: str, approval_notes: str | None, session: SessionContext) -> FilingApproval:
        package, export = self._package_export(package_id, export_id)
        self._require_access(session, package)
        self._require_access(session, export)
        if export.status != "ready_for_download" or export.validation_result.status == "failed":
            raise ValueError("Failed validation blocks approval")
        approval = FilingApproval(
            package_id=package_id,
            export_id=export_id,
            organization_id=package.organization_id or session.organization_id,
            approval_notes=approval_notes,
        )
        return self.approval_repository.save(approval)

    def approve(self, *, approval_id: str, session: SessionContext, approval_notes: str | None = None) -> FilingApproval:
        approval = self._approval(approval_id)
        self._require_reviewer(session, approval.organization_id)
        approval.approval_status = ApprovalStatus.APPROVED
        approval.approver_user_id = session.user_id
        approval.approval_notes = approval_notes or approval.approval_notes
        approval.approved_at = datetime.now(UTC)
        return self.approval_repository.save(approval)

    def reject(self, *, approval_id: str, session: SessionContext, approval_notes: str | None = None) -> FilingApproval:
        approval = self._approval(approval_id)
        self._require_reviewer(session, approval.organization_id)
        approval.approval_status = ApprovalStatus.REJECTED
        approval.approver_user_id = session.user_id
        approval.approval_notes = approval_notes or approval.approval_notes
        approval.rejected_at = datetime.now(UTC)
        return self.approval_repository.save(approval)

    def create_draft(self, *, package_id: str, export_id: str, session: SessionContext) -> FilingSubmission:
        package, export = self._package_export(package_id, export_id)
        self._require_access(session, package)
        self._require_access(session, export)
        config = get_filing_provider_configuration()
        submission = FilingSubmission(
            package_id=package_id,
            export_id=export_id,
            owner_user_id=package.owner_user_id,
            organization_id=package.organization_id,
            created_by=session.user_id,
            provider=config.provider,
            provider_mode=config.provider_mode,
        )
        return self.submission_repository.save(submission)

    def readiness(self, *, submission_id: str, session: SessionContext) -> FilingReadinessResult:
        submission = self._submission(submission_id)
        self._require_access(session, submission)
        return self.readiness_service.check(package_id=submission.package_id, export_id=submission.export_id, session=session)

    def submit(self, *, submission_id: str, session: SessionContext) -> FilingSubmission:
        submission = self._submission(submission_id)
        if session.role == UserRole.SERVICE:
            raise PermissionError("Service role cannot submit arbitrary returns")
        self._require_access(session, submission)
        readiness = self.readiness(submission_id=submission_id, session=session)
        if not readiness.ready:
            submission.submission_status = SubmissionStatus.BLOCKED
            submission.updated_at = datetime.now(UTC)
            self.submission_repository.save(submission)
            raise ValueError(f"Filing submission is blocked: {', '.join(readiness.blockers)}")
        provider = get_filing_provider()
        validation = provider.validate_export_payload(package_id=submission.package_id, export_id=submission.export_id, payload=None)
        if not validation.success:
            submission.submission_status = SubmissionStatus.SUBMISSION_FAILED
            submission.failure_reason = validation.safe_message or validation.failure_reason or "Provider validation failed"
            submission.updated_at = datetime.now(UTC)
            self.submission_repository.save(submission)
            raise ValueError(submission.failure_reason)
        response = provider.submit_return(package_id=submission.package_id, export_id=submission.export_id, payload=None)
        if not response.success or not response.provider_reference_id:
            submission.submission_status = SubmissionStatus.SUBMISSION_FAILED
            submission.failure_reason = response.safe_message or response.failure_reason or "Provider submission failed"
            submission.updated_at = datetime.now(UTC)
            self.submission_repository.save(submission)
            raise ValueError(submission.failure_reason)
        submission.provider = getattr(provider, "provider_name", submission.provider)
        if submission.provider == "eri":
            submission.provider = f"eri_{getattr(provider, 'provider_mode', submission.provider_mode)}"
        submission.provider_mode = getattr(provider, "provider_mode", submission.provider_mode)
        submission.provider_reference_id = response.provider_reference_id
        submission.submission_status = response.normalized_status or (SubmissionStatus.SUBMITTED if response.status == "submitted" else SubmissionStatus.PENDING_VERIFICATION)
        submission.submitted_at = datetime.now(UTC)
        submission.updated_at = datetime.now(UTC)
        return self.submission_repository.save(submission)

    def check_status(self, *, submission_id: str, session: SessionContext) -> FilingSubmission:
        submission = self._submission(submission_id)
        self._require_access(session, submission)
        if not submission.provider_reference_id:
            raise ValueError("Submission has no provider reference")
        response = get_filing_provider().get_submission_status(provider_reference_id=submission.provider_reference_id)
        if response.success and response.status in {status.value for status in SubmissionStatus}:
            submission.submission_status = SubmissionStatus(response.status)
        elif response.success and response.status == "acknowledgement_available":
            submission.submission_status = SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE
        elif not response.success:
            submission.failure_reason = response.failure_reason or "Provider status check failed"
        submission.last_checked_at = datetime.now(UTC)
        submission.updated_at = datetime.now(UTC)
        if submission.submission_status == SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE and submission.acknowledgement_id is None:
            ack_response = get_filing_provider().get_acknowledgement(provider_reference_id=submission.provider_reference_id)
            if ack_response.success and ack_response.acknowledgement_number:
                ack = Acknowledgement(
                    submission_id=submission.submission_id,
                    provider_reference_id=submission.provider_reference_id,
                    acknowledgement_number=ack_response.acknowledgement_number,
                )
                self.acknowledgement_repository.save(ack)
                submission.acknowledgement_id = ack.acknowledgement_id
        return self.submission_repository.save(submission)

    def initiate_everification(self, *, submission_id: str, session: SessionContext) -> FilingSubmission:
        submission = self._submission(submission_id)
        self._require_access(session, submission)
        if not submission.provider_reference_id:
            raise ValueError("Submission has no provider reference")
        provider = get_filing_provider()
        if not provider.supports_everification():
            submission.everification_status = EVerificationStatus.FAILED
            submission.failure_reason = "Provider e-verification is not supported for this mode"
            submission.updated_at = datetime.now(UTC)
            return self.submission_repository.save(submission)
        response = provider.initiate_everification(provider_reference_id=submission.provider_reference_id)
        submission.everification_status = EVerificationStatus(response.status if response.success and response.status in {item.value for item in EVerificationStatus} else "failed")
        submission.updated_at = datetime.now(UTC)
        return self.submission_repository.save(submission)

    def everification_status(self, *, submission_id: str, session: SessionContext) -> FilingSubmission:
        submission = self._submission(submission_id)
        self._require_access(session, submission)
        if submission.provider_reference_id:
            response = get_filing_provider().get_everification_status(provider_reference_id=submission.provider_reference_id)
            if response.success:
                submission.everification_status = EVerificationStatus(response.status)
                submission.updated_at = datetime.now(UTC)
                self.submission_repository.save(submission)
        return submission

    def acknowledgement(self, *, submission_id: str, session: SessionContext) -> Acknowledgement:
        submission = self._submission(submission_id)
        self._require_access(session, submission)
        if not submission.acknowledgement_id:
            raise LookupError("Acknowledgement is not available")
        ack = self.acknowledgement_repository.get(submission.acknowledgement_id)
        if ack is None:
            raise LookupError("Acknowledgement is not available")
        return ack

    def get_submission(self, *, submission_id: str, session: SessionContext) -> FilingSubmission:
        submission = self._submission(submission_id)
        self._require_access(session, submission)
        return submission

    def _package_export(self, package_id: str, export_id: str):
        package = self.package_repository.get(package_id)
        export = self.export_repository.get(export_id)
        if package is None:
            raise LookupError("Filing package not found")
        if export is None:
            raise LookupError("ITR export not found")
        if export.package_id != package.package_id:
            raise ValueError("Export does not belong to filing package")
        return package, export

    def _require_access(self, session: SessionContext, resource) -> None:
        if not self.authorization_service.can_read_filing_package(session, resource).allowed:
            raise PermissionError("Access denied")

    def _require_reviewer(self, session: SessionContext, organization_id: str) -> None:
        if session.organization_id != organization_id or session.role not in {UserRole.REVIEWER, UserRole.ADMIN}:
            raise PermissionError("Reviewer or admin approval required")

    def _consent(self, consent_id: str) -> FilingConsent:
        consent = self.consent_repository.get(consent_id)
        if consent is None:
            raise LookupError("Filing consent not found")
        return consent

    def _approval(self, approval_id: str) -> FilingApproval:
        approval = self.approval_repository.get(approval_id)
        if approval is None:
            raise LookupError("Filing approval not found")
        return approval

    def _submission(self, submission_id: str) -> FilingSubmission:
        submission = self.submission_repository.get(submission_id)
        if submission is None:
            raise LookupError("Filing submission not found")
        return submission

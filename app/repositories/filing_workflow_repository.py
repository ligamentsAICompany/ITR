"""Repositories for filing consent, approval, submission, and acknowledgements."""

from app.core.database import get_json_record, save_json_record
from app.models.filing_approval import FilingApproval
from app.models.filing_consent import FilingConsent
from app.models.filing_submission import Acknowledgement, FilingSubmission

FILING_CONSENT_CACHE: dict[str, FilingConsent] = {}
FILING_APPROVAL_CACHE: dict[str, FilingApproval] = {}
FILING_SUBMISSION_CACHE: dict[str, FilingSubmission] = {}
ACKNOWLEDGEMENT_CACHE: dict[str, Acknowledgement] = {}


class FilingConsentRepository:
    table = "filing_consents"

    def save(self, consent: FilingConsent) -> FilingConsent:
        FILING_CONSENT_CACHE[consent.consent_id] = consent
        save_json_record(self.table, consent.consent_id, consent.model_dump(mode="json"), consent.created_at.isoformat(), consent.created_at.isoformat())
        return consent

    def get(self, consent_id: str) -> FilingConsent | None:
        cached = FILING_CONSENT_CACHE.get(consent_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table, consent_id)
        if payload is None:
            return None
        consent = FilingConsent.model_validate(payload)
        FILING_CONSENT_CACHE[consent.consent_id] = consent
        return consent

    def active_for(self, *, package_id: str, export_id: str, user_id: str, organization_id: str) -> FilingConsent | None:
        return next(
            (
                consent
                for consent in FILING_CONSENT_CACHE.values()
                if consent.package_id == package_id
                and consent.export_id == export_id
                and consent.user_id == user_id
                and consent.organization_id == organization_id
                and consent.is_active
            ),
            None,
        )


class FilingApprovalRepository:
    table = "filing_approvals"

    def save(self, approval: FilingApproval) -> FilingApproval:
        FILING_APPROVAL_CACHE[approval.approval_id] = approval
        save_json_record(self.table, approval.approval_id, approval.model_dump(mode="json"), approval.created_at.isoformat(), approval.created_at.isoformat())
        return approval

    def get(self, approval_id: str) -> FilingApproval | None:
        cached = FILING_APPROVAL_CACHE.get(approval_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table, approval_id)
        if payload is None:
            return None
        approval = FilingApproval.model_validate(payload)
        FILING_APPROVAL_CACHE[approval.approval_id] = approval
        return approval

    def approved_for(self, *, package_id: str, export_id: str, organization_id: str) -> FilingApproval | None:
        return next(
            (
                approval
                for approval in FILING_APPROVAL_CACHE.values()
                if approval.package_id == package_id
                and approval.export_id == export_id
                and approval.organization_id == organization_id
                and approval.approval_status == "approved"
            ),
            None,
        )

    def pending_for(self, *, package_id: str, export_id: str, organization_id: str) -> FilingApproval | None:
        return next(
            (
                approval
                for approval in FILING_APPROVAL_CACHE.values()
                if approval.package_id == package_id
                and approval.export_id == export_id
                and approval.organization_id == organization_id
                and approval.approval_status == "pending"
            ),
            None,
        )


class FilingSubmissionRepository:
    table = "filing_submissions"

    def save(self, submission: FilingSubmission) -> FilingSubmission:
        FILING_SUBMISSION_CACHE[submission.submission_id] = submission
        save_json_record(self.table, submission.submission_id, submission.model_dump(mode="json"), submission.created_at.isoformat(), submission.updated_at.isoformat())
        return submission

    def get(self, submission_id: str) -> FilingSubmission | None:
        cached = FILING_SUBMISSION_CACHE.get(submission_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table, submission_id)
        if payload is None:
            return None
        submission = FilingSubmission.model_validate(payload)
        FILING_SUBMISSION_CACHE[submission.submission_id] = submission
        return submission


class AcknowledgementRepository:
    table = "filing_acknowledgements"

    def save(self, acknowledgement: Acknowledgement) -> Acknowledgement:
        ACKNOWLEDGEMENT_CACHE[acknowledgement.acknowledgement_id] = acknowledgement
        save_json_record(
            self.table,
            acknowledgement.acknowledgement_id,
            acknowledgement.model_dump(mode="json"),
            acknowledgement.created_at.isoformat(),
            acknowledgement.created_at.isoformat(),
        )
        return acknowledgement

    def get(self, acknowledgement_id: str) -> Acknowledgement | None:
        cached = ACKNOWLEDGEMENT_CACHE.get(acknowledgement_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.table, acknowledgement_id)
        if payload is None:
            return None
        acknowledgement = Acknowledgement.model_validate(payload)
        ACKNOWLEDGEMENT_CACHE[acknowledgement.acknowledgement_id] = acknowledgement
        return acknowledgement

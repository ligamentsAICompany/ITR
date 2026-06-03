from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.agents.government_filing_agent import GovernmentFilingAgent
from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.main import app
from app.models.filing_approval import ApprovalStatus
from app.models.filing_consent import ConsentStatus, FilingConsent
from app.models.filing_package import FilingPackage, FilingPackageStatus
from app.models.filing_submission import SubmissionStatus
from app.models.itr_export import ItrExport, ItrExportStatus, OfficialSchemaValidationResult
from app.repositories.audit_repository import AUDIT_EVENT_CACHE
from app.repositories.filing_package_repository import FILING_PACKAGE_CACHE
from app.repositories.filing_workflow_repository import (
    ACKNOWLEDGEMENT_CACHE,
    FILING_APPROVAL_CACHE,
    FILING_CONSENT_CACHE,
    FILING_SUBMISSION_CACHE,
)
from app.repositories.itr_export_repository import ITR_EXPORT_CACHE


client = TestClient(app)

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
REVIEWER = "33333333-3333-4333-8333-333333333333"
SERVICE = "55555555-5555-4555-8555-555555555555"
ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def auth(user_id=USER_A, role="taxpayer", org_id=ORG_A):
    return {
        "X-Demo-User-Id": user_id,
        "X-Demo-User-Role": role,
        "X-Demo-Organization-Id": org_id,
    }


def setup_function():
    rate_limiter.clear()
    FILING_PACKAGE_CACHE.clear()
    ITR_EXPORT_CACHE.clear()
    FILING_CONSENT_CACHE.clear()
    FILING_APPROVAL_CACHE.clear()
    FILING_SUBMISSION_CACHE.clear()
    ACKNOWLEDGEMENT_CACHE.clear()
    AUDIT_EVENT_CACHE.clear()
    get_settings.cache_clear()


def teardown_function():
    rate_limiter.clear()


def save_package(status=FilingPackageStatus.READY_FOR_CA_REVIEW, owner=USER_A, org=ORG_A, package_id=None):
    package = FilingPackage(
        package_id=package_id or "10000000-0000-4000-8000-000000000001",
        owner_user_id=owner,
        organization_id=org,
        created_by=owner,
        assessment_year="2026-27",
        previous_year="2025-26",
        candidate_itr="ITR-1",
        status=status,
        readiness_score=90,
        validation_run_id="20000000-0000-4000-8000-000000000001",
        computation_id="30000000-0000-4000-8000-000000000001",
    )
    FILING_PACKAGE_CACHE[package.package_id] = package
    return package


def save_export(status=ItrExportStatus.READY_FOR_DOWNLOAD, package_id="10000000-0000-4000-8000-000000000001"):
    validation_status = "passed" if status == ItrExportStatus.READY_FOR_DOWNLOAD else "failed"
    export = ItrExport(
        export_id="40000000-0000-4000-8000-000000000001",
        package_id=package_id,
        owner_user_id=USER_A,
        organization_id=ORG_A,
        created_by=USER_A,
        assessment_year="2026-27",
        previous_year="2025-26",
        candidate_itr="ITR-1",
        status=status,
        validation_result=OfficialSchemaValidationResult(
            candidate_itr="ITR-1",
            assessment_year="2026-27",
            status=validation_status,
        ),
    )
    ITR_EXPORT_CACHE[export.export_id] = export
    return export


def create_submission(headers=None):
    package = save_package()
    export = save_export(package_id=package.package_id)
    response = client.post(
        "/v1/filing/submissions",
        json={"package_id": package.package_id, "export_id": export.export_id},
        headers=headers or auth(),
    )
    assert response.status_code == 200, response.text
    return package, export, response.json()


def grant_consent(package, export, headers=None):
    request = client.post(
        "/v1/filing/consents/request",
        json={"package_id": package.package_id, "export_id": export.export_id, "consent_text": "I consent to submit this specific validated export package."},
        headers=headers or auth(),
    )
    assert request.status_code == 200, request.text
    grant = client.post(f"/v1/filing/consents/{request.json()['consent_id']}/grant", json={}, headers=headers or auth())
    assert grant.status_code == 200, grant.text
    return grant.json()


def approve(package, export):
    request = client.post(
        "/v1/filing/approvals/request",
        json={"package_id": package.package_id, "export_id": export.export_id, "approval_notes": "Reviewed deterministic export."},
        headers=auth(REVIEWER, "reviewer", ORG_A),
    )
    assert request.status_code == 200, request.text
    approval = client.post(
        f"/v1/filing/approvals/{request.json()['approval_id']}/approve",
        json={"approval_notes": "Approved after review."},
        headers=auth(REVIEWER, "reviewer", ORG_A),
    )
    assert approval.status_code == 200, approval.text
    return approval.json()


def test_readiness_blocks_missing_consent_export_not_ready_validation_failed_and_approval_pending():
    package, export, submission = create_submission()

    missing_consent = client.post(f"/v1/filing/submissions/{submission['submission_id']}/readiness", json={}, headers=auth())
    assert missing_consent.status_code == 200
    assert missing_consent.json()["ready"] is False
    assert "missing_consent" in missing_consent.json()["blockers"]

    grant_consent(package, export)
    pending_approval = client.post(f"/v1/filing/submissions/{submission['submission_id']}/readiness", json={}, headers=auth())
    assert "approval_pending" in pending_approval.json()["blockers"]

    ITR_EXPORT_CACHE[export.export_id] = export.model_copy(update={"status": ItrExportStatus.SCHEMA_FAILED})
    failed = client.post(f"/v1/filing/submissions/{submission['submission_id']}/readiness", json={}, headers=auth())
    assert "export_not_ready" in failed.json()["blockers"]
    assert "schema_validation_failed" in failed.json()["blockers"]


def test_consent_request_grant_revoke_and_expired_or_revoked_block_submission():
    package, export, submission = create_submission()
    consent = grant_consent(package, export)
    assert consent["consent_status"] == ConsentStatus.GRANTED

    revoked = client.post(f"/v1/filing/consents/{consent['consent_id']}/revoke", json={}, headers=auth())
    assert revoked.status_code == 200
    readiness = client.post(f"/v1/filing/submissions/{submission['submission_id']}/readiness", json={}, headers=auth())
    assert "missing_consent" in readiness.json()["blockers"]

    expired = FilingConsent(
        user_id=USER_A,
        organization_id=ORG_A,
        package_id=package.package_id,
        export_id=export.export_id,
        consent_status=ConsentStatus.GRANTED,
        consent_text="I consent to submit this specific validated export package.",
        granted_at=datetime.now(UTC) - timedelta(days=2),
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    FILING_CONSENT_CACHE[expired.consent_id] = expired
    readiness = client.post(f"/v1/filing/submissions/{submission['submission_id']}/readiness", json={}, headers=auth())
    assert "missing_consent" in readiness.json()["blockers"]


def test_approval_request_approve_reject_and_role_boundaries():
    package, export, _submission = create_submission()
    ITR_EXPORT_CACHE[export.export_id] = export.model_copy(update={"status": ItrExportStatus.NOT_CONFIGURED})
    blocked = client.post(
        "/v1/filing/approvals/request",
        json={"package_id": package.package_id, "export_id": export.export_id},
        headers=auth(),
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "Approval cannot be requested yet because schema export is not ready. Please generate a schema-validated export first."

    ITR_EXPORT_CACHE[export.export_id] = export
    request = client.post(
        "/v1/filing/approvals/request",
        json={"package_id": package.package_id, "export_id": export.export_id},
        headers=auth(),
    )
    assert request.status_code == 200
    approval_id = request.json()["approval_id"]

    taxpayer = client.post(f"/v1/filing/approvals/{approval_id}/approve", json={}, headers=auth())
    different_org = client.post(f"/v1/filing/approvals/{approval_id}/approve", json={}, headers=auth(REVIEWER, "reviewer", ORG_B))
    reviewer = client.post(f"/v1/filing/approvals/{approval_id}/approve", json={}, headers=auth(REVIEWER, "reviewer", ORG_A))
    reject = client.post(
        "/v1/filing/approvals/request",
        json={"package_id": package.package_id, "export_id": export.export_id},
        headers=auth(REVIEWER, "reviewer", ORG_A),
    )
    rejected = client.post(f"/v1/filing/approvals/{reject.json()['approval_id']}/reject", json={}, headers=auth(REVIEWER, "reviewer", ORG_A))

    assert taxpayer.status_code == 403
    assert different_org.status_code == 403
    assert reviewer.status_code == 200
    assert reviewer.json()["approval_status"] == ApprovalStatus.APPROVED
    assert rejected.status_code == 200
    assert rejected.json()["approval_status"] == ApprovalStatus.REJECTED


def test_mock_submission_status_everification_and_acknowledgement_lifecycle():
    package, export, submission = create_submission()
    blocked = client.post(f"/v1/filing/submissions/{submission['submission_id']}/submit", json={}, headers=auth())
    grant_consent(package, export)
    approve(package, export)

    early_ack = client.get(f"/v1/filing/submissions/{submission['submission_id']}/acknowledgement", headers=auth())
    submitted = client.post(f"/v1/filing/submissions/{submission['submission_id']}/submit", json={}, headers=auth())
    status = client.post(f"/v1/filing/submissions/{submission['submission_id']}/status-check", json={}, headers=auth())
    everify = client.post(f"/v1/filing/submissions/{submission['submission_id']}/everification/initiate", json={}, headers=auth())
    everify_status = client.get(f"/v1/filing/submissions/{submission['submission_id']}/everification", headers=auth())
    ack = client.get(f"/v1/filing/submissions/{submission['submission_id']}/acknowledgement", headers=auth())

    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "Submission is not ready yet. Complete consent, reviewer approval, and export validation first."
    assert early_ack.status_code == 404
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["submission_status"] == SubmissionStatus.SUBMITTED
    assert submitted.json()["provider_mode"] == "mock"
    assert status.json()["submission_status"] == SubmissionStatus.ACKNOWLEDGEMENT_AVAILABLE
    assert everify.status_code == 200
    assert everify_status.json()["everification_status"] in {"initiated", "pending", "verified"}
    assert ack.status_code == 200
    assert ack.json()["acknowledgement_number"].startswith("MOCK-ACK-")


def test_readiness_and_submit_use_persisted_consent_and_approval_after_cache_miss(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
    monkeypatch.setenv("PERSISTENCE_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    package, export, submission = create_submission()
    grant_consent(package, export)
    approve(package, export)

    FILING_CONSENT_CACHE.clear()
    FILING_APPROVAL_CACHE.clear()

    readiness = client.post(f"/v1/filing/submissions/{submission['submission_id']}/readiness", json={}, headers=auth())
    submitted = client.post(f"/v1/filing/submissions/{submission['submission_id']}/submit", json={}, headers=auth())

    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
    assert readiness.json()["blockers"] == []
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["provider_reference_id"].startswith("MOCK-")


def test_mock_submission_failure_and_live_or_missing_provider_fail_safely(monkeypatch):
    package, export, submission = create_submission()
    grant_consent(package, export)
    approve(package, export)

    monkeypatch.setenv("MOCK_FILING_OUTCOME", "failure")
    get_settings.cache_clear()
    failed = client.post(f"/v1/filing/submissions/{submission['submission_id']}/submit", json={}, headers=auth())
    assert failed.status_code == 400
    assert "provider rejected" in failed.json()["detail"].lower()

    monkeypatch.setenv("FILING_PROVIDER", "live")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "live")
    monkeypatch.delenv("ALLOW_LIVE_FILING", raising=False)
    get_settings.cache_clear()
    live = client.post(f"/v1/filing/submissions/{submission['submission_id']}/readiness", json={}, headers=auth())
    assert "live_filing_disabled" in live.json()["blockers"]

    monkeypatch.setenv("FILING_PROVIDER", "sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    monkeypatch.delenv("ERI_CLIENT_ID", raising=False)
    monkeypatch.delenv("ERI_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    sandbox = client.post(f"/v1/filing/submissions/{submission['submission_id']}/readiness", json={}, headers=auth())
    assert "provider_not_configured" in sandbox.json()["blockers"]


def test_cross_user_service_role_sensitive_data_and_agent_boundaries():
    package, export, submission = create_submission()
    grant_consent(package, export)
    approve(package, export)

    cross_user = client.get(f"/v1/filing/submissions/{submission['submission_id']}", headers=auth(USER_B, "taxpayer", ORG_A))
    service_submit = client.post(
        f"/v1/filing/submissions/{submission['submission_id']}/submit",
        json={},
        headers=auth(SERVICE, "service", ORG_A),
    )
    agent_text = GovernmentFilingAgent().explain_submission(submission["submission_id"], session_user_id=USER_A)

    assert cross_user.status_code == 403
    assert service_submit.status_code == 403
    assert "submit" not in agent_text.explanation.lower() or "cannot" in agent_text.explanation.lower()
    assert "ABCDE1234F" not in str([event.metadata_summary for event in AUDIT_EVENT_CACHE.values()])
    assert "123456789012" not in str([event.metadata_summary for event in AUDIT_EVENT_CACHE.values()])
    assert {"filing_consent_granted", "filing_approval_approved"}.issubset(
        {event.event_type for event in AUDIT_EVENT_CACHE.values()}
    )

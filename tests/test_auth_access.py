from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.repositories.audit_repository import AUDIT_EVENT_CACHE


client = TestClient(app)

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
REVIEWER = "33333333-3333-4333-8333-333333333333"
ADMIN = "44444444-4444-4444-8444-444444444444"
ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def auth(user_id=USER_A, role="taxpayer", org_id=ORG_A):
    return {
        "X-Demo-User-Id": user_id,
        "X-Demo-User-Role": role,
        "X-Demo-Organization-Id": org_id,
    }


def test_production_missing_auth_is_rejected(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DEMO_AUTH_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        response = client.post(
            "/v1/uploads",
            data={"document_type": "form16"},
            files={"file": ("form16.csv", b"Gross Salary\n1200000\n", "text/csv")},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 401


def test_production_demo_headers_are_rejected_when_demo_auth_disabled(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DEMO_AUTH_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        response = client.post(
            "/v1/uploads",
            data={"document_type": "form16"},
            files={"file": ("form16.csv", b"Gross Salary\n1200000\n", "text/csv")},
            headers=auth(USER_A, "taxpayer", ORG_A),
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 401


def test_invalid_demo_role_is_rejected():
    response = client.post(
        "/v1/uploads",
        data={"document_type": "form16"},
        files={"file": ("form16.csv", b"Gross Salary\n1200000\n", "text/csv")},
        headers=auth(role="superuser"),
    )

    assert response.status_code in {400, 403}


def test_taxpayer_can_read_own_upload_and_cross_user_is_denied(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        upload = client.post(
            "/v1/uploads",
            data={"document_type": "form16"},
            files={"file": ("form16.csv", b"Gross Salary\n1200000\n", "text/csv")},
            headers=auth(USER_A, "taxpayer", ORG_A),
        )
        assert upload.status_code == 200, upload.text
        document_id = upload.json()["document_id"]

        own = client.get(f"/v1/uploads/{document_id}", headers=auth(USER_A, "taxpayer", ORG_A))
        cross_user = client.get(f"/v1/uploads/{document_id}", headers=auth(USER_B, "taxpayer", ORG_A))
        same_org_reviewer = client.get(f"/v1/uploads/{document_id}", headers=auth(REVIEWER, "reviewer", ORG_A))
        cross_org_reviewer = client.get(f"/v1/uploads/{document_id}", headers=auth(REVIEWER, "reviewer", ORG_B))
        same_org_admin = client.get(f"/v1/uploads/{document_id}", headers=auth(ADMIN, "admin", ORG_A))
        cross_org_admin = client.get(f"/v1/uploads/{document_id}", headers=auth(ADMIN, "admin", ORG_B))
    finally:
        get_settings.cache_clear()

    assert own.status_code == 200
    assert "owner_user_id" not in own.text
    assert "storage_path" not in own.text
    assert cross_user.status_code == 403
    assert same_org_reviewer.status_code == 200
    assert cross_org_reviewer.status_code == 403
    assert same_org_admin.status_code == 200
    assert cross_org_admin.status_code == 403


def test_filing_package_artifact_access_and_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSISTENCE_STORAGE_DIR", str(tmp_path / "persistence"))
    get_settings.cache_clear()
    AUDIT_EVENT_CACHE.clear()
    try:
        package = client.post("/v1/filing-packages/generate", json=filing_payload(), headers=auth(USER_A)).json()
        artifact_id = package["artifacts"][0]["artifact_id"]

        own_download = client.get(
            f"/v1/filing-packages/{package['package_id']}/artifacts/{artifact_id}",
            headers=auth(USER_A),
        )
        denied = client.get(
            f"/v1/filing-packages/{package['package_id']}/artifacts/{artifact_id}",
            headers=auth(USER_B),
        )
    finally:
        get_settings.cache_clear()

    assert own_download.status_code == 200
    assert denied.status_code == 403
    event_types = {event.event_type for event in AUDIT_EVENT_CACHE.values()}
    assert "filing_package_generated" in event_types
    assert "artifact_downloaded" in event_types
    assert "access_denied" in event_types
    assert "ABCDE1234F" not in str([event.metadata_summary for event in AUDIT_EVENT_CACHE.values()])
    assert "123456789012" not in str([event.metadata_summary for event in AUDIT_EVENT_CACHE.values()])


def test_invalid_backends_fail_safely(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "oracle")
    get_settings.cache_clear()
    try:
        persistence_response = client.post("/v1/validation/run", json=validation_payload(), headers=auth(USER_A))
    finally:
        get_settings.cache_clear()

    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    get_settings.cache_clear()
    try:
        storage_response = client.post(
            "/v1/uploads",
            data={"document_type": "form16"},
            files={"file": ("form16.csv", b"Gross Salary\n1200000\n", "text/csv")},
            headers=auth(USER_A),
        )
    finally:
        get_settings.cache_clear()

    assert persistence_response.status_code == 500
    assert storage_response.status_code == 500


def validation_payload():
    return {
        "profile_id": "profile-test",
        "session_id": "session-test",
        "profile": sample_profile(),
        "documents": [],
        "extractions": [],
        "approved_field_ids": [],
    }


def filing_payload():
    validation = {
        "validation_run_id": "55555555-5555-4555-8555-555555555555",
        "profile_id": "profile-test",
        "session_id": "session-test",
        "created_at": "2026-05-30T00:00:00Z",
        "overall_status": "passed",
        "readiness_score": 100,
        "issues": [],
        "missing_fields": [],
        "conflicts": [],
        "warnings": ["PAN ABCDE1234F and Aadhaar 123456789012 require review."],
        "evidence_summary": {"document_count": 0, "approved_extracted_field_count": 0, "document_types": []},
    }
    tax = {
        "computation_id": "66666666-6666-4666-8666-666666666666",
        "assessment_year": "2026-27",
        "previous_year": "2025-26",
        "selected_regime": "new",
        "regime_label": "New regime",
        "default_regime": "new",
        "candidate_itr": "ITR-1",
        "is_preview": False,
        "income": {
            "salary_income": 1200000,
            "standard_deduction": 75000,
            "house_property_income": 0,
            "business_profession_income": 0,
            "capital_gains_income": 0,
            "capital_gains_subtypes": {},
            "other_sources_income": 0,
            "gross_total_income": 1200000,
        },
        "deductions": {"claimed_total": 0, "allowed_total": 0, "disallowed_total": 0, "applied": []},
        "taxable_income": 1125000,
        "tax_before_rebate": 52500,
        "rebate": 52500,
        "surcharge": 0,
        "cess": 0,
        "total_tax_liability": 0,
        "credits": {"tds_salary": 50000, "tds_other": 0, "tcs": 0, "advance_tax": 0, "self_assessment_tax": 0, "total_credits": 50000},
        "refund_due": 50000,
        "tax_payable": 0,
        "warnings": [],
        "steps": [],
    }
    return {
        "profile": sample_profile(),
        "candidate_itr": {
            "candidate_itr": "ITR-1",
            "reason_codes": ["ITR1_ELIGIBLE_SIMPLE_RESIDENT_INDIVIDUAL"],
            "missing_fields": [],
            "confidence": "high",
        },
        "validation_report": validation,
        "tax_computation_result": tax,
        "documents": [],
    }


def sample_profile():
    return {
        "schema_version": "canonical-tax-profile/v0.2",
        "assessment_year": "2026-27",
        "previous_year": "2025-26",
        "return_filing_reason": {"type": "voluntary"},
        "is_defective_return_case": "no",
        "user_identity": {"pan": "ABCDE1234F", "aadhaar_number": "123456789012"},
        "entity_type": "individual",
        "residency_status": {"status": "resident"},
        "income_heads": {
            "salary": {"has_income": "yes", "gross_amount": 1200000, "employer_name": "Example Pvt Ltd"},
            "house_property": {"has_income": "no", "gross_amount": 0},
            "capital_gains": {"has_income": "no", "gross_amount": 0},
            "business_profession": {"has_income": "no", "gross_amount": 0, "presumptive_taxation": "no"},
            "other_sources": {"has_income": "no", "gross_amount": 0},
        },
        "deductions": {"has_deductions": "no", "section_claims": []},
        "tax_payments": {"tds_salary": 50000, "tds_other": 0, "tcs": 0, "advance_tax": 0, "self_assessment_tax": 0},
        "foreign_assets": {"has_foreign_assets": "no", "has_foreign_income": "no"},
        "exemptions_flags": {
            "claims_section_11_exemption": "no",
            "trust_or_institution_case": "no",
            "political_party_case": "no",
            "university_or_research_case": "no",
        },
        "special_conditions": {
            "director_in_company": "no",
            "unlisted_equity_held": "no",
            "brought_forward_losses": "no",
            "esop_tax_deferred": "no",
            "audit_required": "no",
            "presumptive_taxation_ambiguity": "no",
            "business_profession_ambiguity": "no",
            "capital_gains_edge_case": "no",
            "evidence_mismatch": "no",
            "low_confidence_extraction": "no",
            "pack_resolution_conflict": "no",
        },
    }

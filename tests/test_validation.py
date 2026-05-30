from fastapi.testclient import TestClient

from app.main import app
from app.services.storage_service import LocalStorageService


client = TestClient(app)


def sample_profile(**overrides):
    profile = {
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
            "business_profession": {
                "has_income": "no",
                "gross_amount": 0,
                "presumptive_taxation": "no",
            },
            "other_sources": {
                "has_income": "yes",
                "gross_amount": 4200,
                "has_interest_income": "yes",
                "interest_savings_amount": 4200,
            },
        },
        "deductions": {"has_deductions": "no", "section_claims": []},
        "tax_payments": {"tds_salary": 125000, "tds_other": 0},
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
    deep_merge(profile, overrides)
    return profile


def deep_merge(target, overrides):
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = value


def document(document_id="doc-form16", document_type="form16"):
    return {
        "document_id": document_id,
        "document_type": document_type,
        "original_filename": f"{document_type}.csv",
        "safe_filename": f"{document_type}.csv",
        "size": 128,
        "mime_type": "text/csv",
        "sha256": "a" * 64,
        "status": "extracted",
        "uploaded_at": "2026-05-30T00:00:00Z",
    }


def extraction(document_id, field_id, canonical_path, value, confidence=0.98):
    return {
        "document_id": document_id,
        "status": "completed",
        "fields": [
            {
                "field_id": field_id,
                "label": canonical_path,
                "value": value,
                "raw_path": canonical_path,
                "canonical_path": canonical_path,
                "confidence": confidence,
                "source": {"document_id": document_id, "locator": "csv:1"},
            }
        ],
    }


def run_validation(profile=None, documents=None, extractions=None, approved_field_ids=None):
    response = client.post(
        "/v1/validation/run",
        json={
            "profile_id": "profile-test",
            "session_id": "session-test",
            "profile": profile or sample_profile(),
            "documents": documents if documents is not None else [document()],
            "extractions": extractions if extractions is not None else [],
            "approved_field_ids": approved_field_ids or [],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def issue_by_rule(report, rule_id):
    return next(issue for issue in report["issues"] if issue["rule_id"] == rule_id)


def test_upload_metadata_response_does_not_expose_storage_path(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))

    response = client.post(
        "/v1/uploads",
        data={"document_type": "form16"},
        files={"file": ("form16.csv", b"Gross Salary\n1200000\n", "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "document_id",
        "document_type",
        "original_filename",
        "safe_filename",
        "size",
        "mime_type",
        "sha256",
        "status",
        "uploaded_at",
    }
    assert "storage_path" not in payload
    internal = LocalStorageService(tmp_path).get(payload["document_id"])
    assert internal.storage_path


def test_pan_mismatch_is_critical_and_masked():
    report = run_validation(
        documents=[document("doc-form16")],
        extractions=[
            extraction("doc-form16", "pan-1", "user_identity.pan", "ZZZZZ9999Z"),
        ],
        approved_field_ids=["pan-1"],
    )

    issue = issue_by_rule(report, "identity.pan_mismatch")
    assert issue["severity"] == "critical"
    assert issue["blocks_filing_package"] is True
    assert "ABCDE1234F" not in str(issue)
    assert "ZZZZZ9999Z" not in str(issue)
    assert "****" in issue["message"]
    assert report["overall_status"] == "failed"


def test_salary_mismatch_is_high_conflict():
    report = run_validation(
        extractions=[
            extraction("doc-form16", "salary-1", "income_heads.salary.gross_amount", 1400000),
        ],
        approved_field_ids=["salary-1"],
    )

    issue = issue_by_rule(report, "reconciliation.salary_mismatch")
    assert issue["severity"] == "high"
    assert issue["field_path"] == "income_heads.salary.gross_amount"
    assert report["conflicts"][0]["field_path"] == "income_heads.salary.gross_amount"
    assert report["conflicts"][0]["source_confidences"] == [0.98]


def test_tds_mismatch_is_high_conflict():
    report = run_validation(
        documents=[document("doc-ais", "ais")],
        extractions=[
            extraction("doc-ais", "tds-1", "tax_payments.tds_salary", 99000),
        ],
        approved_field_ids=["tds-1"],
    )

    assert issue_by_rule(report, "reconciliation.tds_mismatch")["severity"] == "high"


def test_missing_form16_salary_is_medium_when_salary_declared():
    report = run_validation(documents=[], extractions=[])

    issue = issue_by_rule(report, "documents.missing_form16_salary")
    assert issue["severity"] == "medium"
    assert report["overall_status"] == "warning"


def test_missing_ais_or_26as_with_tds_is_medium():
    report = run_validation(documents=[document("doc-form16", "form16")])

    assert issue_by_rule(report, "documents.missing_ais_26as_tds")["severity"] == "medium"


def test_interest_income_mismatch_is_medium_conflict():
    report = run_validation(
        documents=[document("doc-bank", "bank_statement")],
        extractions=[
            extraction(
                "doc-bank",
                "interest-1",
                "income_heads.other_sources.interest_savings_amount",
                9000,
            ),
        ],
        approved_field_ids=["interest-1"],
    )

    assert issue_by_rule(report, "reconciliation.interest_mismatch")["severity"] == "medium"


def test_deduction_claimed_without_evidence_is_medium():
    report = run_validation(
        sample_profile(deductions={"has_deductions": "yes", "section_claims": [{"section_code": "80C", "amount": 150000}]}),
        documents=[],
        extractions=[],
    )

    assert issue_by_rule(report, "evidence.deduction_missing")["severity"] == "medium"


def test_capital_gains_without_support_is_medium():
    report = run_validation(
        sample_profile(
            income_heads={
                "capital_gains": {
                    "has_income": "yes",
                    "gross_amount": 50000,
                    "has_ltcg_112a": "yes",
                    "ltcg_112a_amount": 50000,
                }
            }
        ),
        documents=[],
        extractions=[],
    )

    assert issue_by_rule(report, "evidence.capital_gains_missing")["severity"] == "medium"


def test_foreign_assets_requires_high_expert_review():
    report = run_validation(sample_profile(foreign_assets={"has_foreign_assets": "yes", "has_foreign_income": "no"}))

    issue = issue_by_rule(report, "review.foreign_assets_income")
    assert issue["severity"] == "high"
    assert issue["status"] == "needs_review"
    assert report["overall_status"] == "needs_review"


def test_approved_low_confidence_extraction_warns_without_auto_merging():
    report = run_validation(
        documents=[document("doc-form16", "form16"), document("doc-ais", "ais")],
        extractions=[
            extraction("doc-form16", "salary-1", "income_heads.salary.gross_amount", 1200000, confidence=0.4),
        ],
        approved_field_ids=["salary-1"],
    )

    issue = issue_by_rule(report, "evidence.low_confidence_extraction")
    assert issue["severity"] == "low"
    assert issue["source_documents"] == ["doc-form16"]
    assert report["overall_status"] == "warning"
    assert report["readiness_score"] == 97


def test_no_document_manual_warning_does_not_crash_or_fail():
    report = run_validation(sample_profile(income_heads={"salary": {"has_income": "no", "gross_amount": 0}}), documents=[])

    assert report["validation_run_id"]
    assert report["overall_status"] in {"passed", "warning"}
    assert all(issue["severity"] != "critical" for issue in report["issues"])


def test_clean_matching_profile_passes():
    report = run_validation(
        documents=[document("doc-form16", "form16"), document("doc-ais", "ais"), document("doc-bank", "bank_statement")],
        extractions=[
            extraction("doc-form16", "salary-1", "income_heads.salary.gross_amount", 1200000),
            extraction("doc-ais", "tds-1", "tax_payments.tds_salary", 125000),
            extraction("doc-bank", "interest-1", "income_heads.other_sources.interest_savings_amount", 4200),
        ],
        approved_field_ids=["salary-1", "tds-1", "interest-1"],
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_score"] == 100
    assert report["issues"] == []


def test_readiness_score_uses_severity_policy():
    report = run_validation(
        documents=[],
        extractions=[
            extraction("doc-form16", "salary-1", "income_heads.salary.gross_amount", 1400000),
        ],
        approved_field_ids=["salary-1"],
    )

    assert report["readiness_score"] == 60


def test_validation_api_get_shape_and_explanation_are_grounded():
    report = run_validation(
        extractions=[
            extraction("doc-form16", "salary-1", "income_heads.salary.gross_amount", 1400000),
        ],
        approved_field_ids=["salary-1"],
    )

    get_response = client.get(f"/v1/validation/{report['validation_run_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["validation_run_id"] == report["validation_run_id"]

    explain_response = client.post(
        "/v1/validation/explain",
        json={"validation_run_id": report["validation_run_id"]},
    )
    assert explain_response.status_code == 200
    payload = explain_response.json()
    assert payload["validation_run_id"] == report["validation_run_id"]
    assert "salary" in payload["explanation"].lower()
    assert "ITR-1" not in payload["explanation"]
    assert "should file" not in payload["explanation"].lower()

import json
import zipfile
from copy import deepcopy
from decimal import Decimal
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.models.decision import ITRDecisionResponse
from app.models.tax_computation import (
    DeductionBreakdown,
    IncomeBreakdown,
    TaxComputationResult,
    TaxCreditBreakdown,
)
from app.models.validation import ValidationReport, ValidationStatus
from app.repositories.audit_repository import AUDIT_EVENT_CACHE
from app.repositories.itr_export_repository import ITR_EXPORT_ARTIFACT_CACHE, ITR_EXPORT_CACHE
from app.repositories.schema_pack_repository import SCHEMA_PACK_CACHE, SCHEMA_PACK_CONTENT_CACHE
from app.services.itr_export_service import ItrExportService


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


def setup_function():
    SCHEMA_PACK_CACHE.clear()
    SCHEMA_PACK_CONTENT_CACHE.clear()
    ITR_EXPORT_CACHE.clear()
    ITR_EXPORT_ARTIFACT_CACHE.clear()
    AUDIT_EVENT_CACHE.clear()


def sample_schema(required=None, field_map=None):
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": required or ["assessment_year", "itr_form", "taxable_income"],
        "properties": {
            "assessment_year": {"type": "string"},
            "previous_year": {"type": "string"},
            "itr_form": {"type": "string", "enum": ["ITR-1", "ITR-2", "ITR-3", "ITR-4"]},
            "taxable_income": {"type": "number"},
            "total_tax_liability": {"type": "number"},
            "unsupported_required": {"type": "string"},
        },
        "x-itr": {
            "assessment_year": "2026-27",
            "previous_year": "2025-26",
            "itr_form": "ITR-1",
            "schema_version": "test-v1",
        },
        "x-itr-field-map": field_map or {},
    }


def upload_schema(schema=None, filename="itr1-schema.json", headers=None):
    content = json.dumps(schema or sample_schema()).encode("utf-8")
    return client.post(
        "/v1/schema-packs/upload",
        files={"file": (filename, content, "application/json")},
        headers=headers or auth(ADMIN, "admin", ORG_A),
    )


def upload_schema_zip(schema=None):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("nested/itr1-schema.json", json.dumps(schema or sample_schema()))
    return client.post(
        "/v1/schema-packs/upload",
        files={"file": ("schema-pack.zip", buffer.getvalue(), "application/zip")},
        headers=auth(ADMIN, "admin", ORG_A),
    )


def activate(pack_id):
    return client.post(f"/v1/schema-packs/{pack_id}/activate", headers=auth(ADMIN, "admin", ORG_A))


def profile(**overrides):
    payload = {
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
    deep_merge(payload, overrides)
    return payload


def deep_merge(target, overrides):
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = value


def decision(candidate_itr="ITR-1"):
    return ITRDecisionResponse(
        candidate_itr=candidate_itr,
        reason_codes=["ITR1_ELIGIBLE_SIMPLE_RESIDENT_INDIVIDUAL"],
        missing_fields=[],
        confidence="high",
    )


def validation(status=ValidationStatus.PASSED):
    return ValidationReport(
        validation_run_id="11111111-1111-4111-8111-111111111111",
        profile_id="profile-test",
        session_id="session-test",
        overall_status=status,
        readiness_score=100,
        issues=[],
        missing_fields=[],
        conflicts=[],
        warnings=[],
        evidence_summary={"document_count": 0, "approved_extracted_field_count": 0, "document_types": []},
    )


def tax_result():
    return TaxComputationResult(
        computation_id="22222222-2222-4222-8222-222222222222",
        assessment_year="2026-27",
        previous_year="2025-26",
        selected_regime="new",
        regime_label="New regime",
        default_regime="new",
        candidate_itr="ITR-1",
        is_preview=False,
        income=IncomeBreakdown(
            salary_income=Decimal("1200000"),
            standard_deduction=Decimal("75000"),
            house_property_income=Decimal("0"),
            business_profession_income=Decimal("0"),
            capital_gains_income=Decimal("0"),
            other_sources_income=Decimal("0"),
            gross_total_income=Decimal("1200000"),
        ),
        deductions=DeductionBreakdown(claimed_total=Decimal("0"), allowed_total=Decimal("0"), disallowed_total=Decimal("0"), applied=[]),
        taxable_income=Decimal("1125000"),
        tax_before_rebate=Decimal("52500"),
        rebate=Decimal("52500"),
        surcharge=Decimal("0"),
        cess=Decimal("0"),
        total_tax_liability=Decimal("0"),
        credits=TaxCreditBreakdown(
            tds_salary=Decimal("50000"),
            tds_other=Decimal("0"),
            tcs=Decimal("0"),
            advance_tax=Decimal("0"),
            self_assessment_tax=Decimal("0"),
            total_credits=Decimal("50000"),
        ),
        refund_due=Decimal("50000"),
        tax_payable=Decimal("0"),
        warnings=[],
        steps=[],
    )


def export_payload(package_id=None, candidate=None):
    payload = {
        "profile": profile(),
        "candidate_itr": (candidate or decision()).model_dump(mode="json"),
        "validation_report": validation().model_dump(mode="json"),
        "tax_computation_result": tax_result().model_dump(mode="json"),
    }
    if package_id:
        payload["package_id"] = package_id
    return payload


def test_schema_pack_upload_requires_admin_and_accepts_json_and_zip():
    nonadmin = upload_schema(headers=auth(USER_A, "taxpayer", ORG_A))
    valid_json = upload_schema()
    valid_zip = upload_schema_zip()
    listed = client.get("/v1/schema-packs", headers=auth(ADMIN, "admin", ORG_A))

    assert nonadmin.status_code == 403
    assert valid_json.status_code == 200, valid_json.text
    assert valid_zip.status_code == 200, valid_zip.text
    assert valid_json.json()["source_filename"] == "itr1-schema.json"
    assert "source_content" not in valid_json.text
    assert listed.status_code == 200
    assert len(listed.json()) == 2


def test_schema_pack_upload_rejects_invalid_unsupported_and_nonadmin_activation():
    invalid = client.post(
        "/v1/schema-packs/upload",
        files={"file": ("schema.json", b"{not json", "application/json")},
        headers=auth(ADMIN, "admin", ORG_A),
    )
    unsupported = client.post(
        "/v1/schema-packs/upload",
        files={"file": ("schema.txt", b"{}", "text/plain")},
        headers=auth(ADMIN, "admin", ORG_A),
    )
    pack = upload_schema().json()
    nonadmin_activation = client.post(f"/v1/schema-packs/{pack['schema_pack_id']}/activate", headers=auth(USER_A))

    assert invalid.status_code == 400
    assert unsupported.status_code == 400
    assert nonadmin_activation.status_code == 403


def test_no_active_schema_pack_returns_not_configured_and_no_artifact():
    response = client.post("/v1/itr-exports/generate", json=export_payload(), headers=auth(USER_A))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "not_configured"
    assert payload["validation_result"]["status"] == "not_configured"
    assert payload["artifacts"] == []


def test_mapping_missing_required_field_is_blocked_before_artifact_generation():
    pack = upload_schema(sample_schema(required=["assessment_year", "unsupported_required"])).json()
    activate(pack["schema_pack_id"])

    response = client.post("/v1/itr-exports/generate", json=export_payload(), headers=auth(USER_A))

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["artifacts"] == []
    assert any(error["code"] == "missing_mapping" for error in payload["validation_result"]["errors"])


def test_schema_validation_failure_is_schema_failed_without_artifact():
    schema = sample_schema(field_map={"taxable_income": "selected_regime"})
    pack = upload_schema(schema).json()
    activate(pack["schema_pack_id"])

    response = client.post("/v1/itr-exports/generate", json=export_payload(), headers=auth(USER_A))

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "schema_failed"
    assert payload["artifacts"] == []
    assert payload["validation_result"]["status"] == "failed"
    assert "ABCDE1234F" not in response.text
    assert "123456789012" not in response.text


def test_schema_pass_generates_downloadable_safe_artifact_and_audit_events():
    pack = upload_schema().json()
    activate(pack["schema_pack_id"])

    response = client.post("/v1/itr-exports/generate", json=export_payload(), headers=auth(USER_A))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ready_for_download"
    assert payload["validation_result"]["status"] == "passed"
    assert len(payload["artifacts"]) == 1
    assert "ABCDE1234F" not in response.text
    assert "123456789012" not in response.text
    assert ":" not in payload["artifacts"][0]["filename"]
    content = client.get(
        f"/v1/itr-exports/{payload['export_id']}/artifacts/{payload['artifacts'][0]['artifact_id']}",
        headers=auth(USER_A),
    )
    assert content.status_code == 200
    assert content.json()["itr_form"] == "ITR-1"
    assert "submitted" not in content.text.lower()
    event_types = {event.event_type for event in AUDIT_EVENT_CACHE.values()}
    assert {"schema_pack_uploaded", "schema_pack_activated", "itr_export_generated", "itr_export_downloaded"}.issubset(event_types)


def test_export_ids_and_ownership_are_enforced():
    pack = upload_schema().json()
    activate(pack["schema_pack_id"])
    export = client.post("/v1/itr-exports/generate", json=export_payload(), headers=auth(USER_A)).json()

    own = client.get(f"/v1/itr-exports/{export['export_id']}", headers=auth(USER_A))
    cross_user = client.get(f"/v1/itr-exports/{export['export_id']}", headers=auth(USER_B, "taxpayer", ORG_A))
    same_org_reviewer = client.get(f"/v1/itr-exports/{export['export_id']}", headers=auth(REVIEWER, "reviewer", ORG_A))
    cross_org_reviewer = client.get(f"/v1/itr-exports/{export['export_id']}", headers=auth(REVIEWER, "reviewer", ORG_B))
    unknown = client.get("/v1/itr-exports/99999999-9999-4999-8999-999999999999", headers=auth(USER_A))

    assert own.status_code == 200
    assert cross_user.status_code == 403
    assert same_org_reviewer.status_code == 200
    assert cross_org_reviewer.status_code == 403
    assert unknown.status_code == 404


def test_validate_and_explain_are_grounded_and_never_claim_submission():
    pack = upload_schema().json()
    activate(pack["schema_pack_id"])
    export = client.post("/v1/itr-exports/generate", json=export_payload(), headers=auth(USER_A)).json()

    validate_response = client.post("/v1/itr-exports/validate", json=export_payload(), headers=auth(USER_A))
    explain_response = client.post("/v1/itr-exports/explain", json={"export_id": export["export_id"]}, headers=auth(USER_A))

    assert validate_response.status_code == 200
    assert validate_response.json()["status"] == "passed"
    assert explain_response.status_code == 200
    explanation = explain_response.json()["explanation"].lower()
    assert "schema validation passed" in explanation
    assert "filed" not in explanation
    assert "accepted" not in explanation
    assert "submitted" not in explanation


def test_schema_activation_makes_previous_pack_inactive():
    first = upload_schema(sample_schema(field_map={"taxable_income": "profile.taxpayer_master.full_name"})).json()
    second = upload_schema(sample_schema()).json()
    activate(first["schema_pack_id"])
    activate(second["schema_pack_id"])

    packs = client.get("/v1/schema-packs", headers=auth(ADMIN, "admin", ORG_A)).json()
    active = [pack for pack in packs if pack["is_active"]]

    assert [pack["schema_pack_id"] for pack in active] == [second["schema_pack_id"]]


def test_service_does_not_mutate_inputs():
    pack = upload_schema().json()
    activate(pack["schema_pack_id"])
    original_profile = profile()
    copied = deepcopy(original_profile)

    ItrExportService().generate(
        profile=original_profile,
        candidate_itr=decision(),
        validation_report=validation(),
        tax_computation_result=tax_result(),
        owner_user_id=USER_A,
        organization_id=ORG_A,
        created_by=USER_A,
    )

    assert original_profile == copied

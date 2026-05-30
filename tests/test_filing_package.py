from copy import deepcopy
from decimal import Decimal

from fastapi.testclient import TestClient

from app.agents.filing_agent import FilingAgent
from app.main import app
from app.models.decision import ITRDecisionResponse
from app.models.filing_package import FilingPackageStatus
from app.models.tax_computation import (
    DeductionBreakdown,
    IncomeBreakdown,
    TaxComputationResult,
    TaxComputationWarning,
    TaxCreditBreakdown,
)
from app.models.validation import ValidationReport, ValidationStatus
from app.repositories.filing_package_repository import FilingPackageRepository
from app.services.filing_package_service import FilingPackageService


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
    deep_merge(profile, overrides)
    return profile


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


def validation(status=ValidationStatus.PASSED, readiness_score=100):
    return ValidationReport(
        validation_run_id="11111111-1111-4111-8111-111111111111",
        profile_id="profile-test",
        session_id="session-test",
        overall_status=status,
        readiness_score=readiness_score,
        issues=[],
        missing_fields=[],
        conflicts=[],
        warnings=[],
        evidence_summary={"document_count": 1, "approved_extracted_field_count": 1, "document_types": ["form16"]},
    )


def tax_result(warnings=None, is_preview=False):
    return TaxComputationResult(
        computation_id="22222222-2222-4222-8222-222222222222",
        assessment_year="2026-27",
        previous_year="2025-26",
        selected_regime="new",
        regime_label="New regime",
        default_regime="new",
        candidate_itr="ITR-1",
        is_preview=is_preview,
        income=IncomeBreakdown(
            salary_income=Decimal("1200000"),
            standard_deduction=Decimal("75000"),
            house_property_income=Decimal("0"),
            business_profession_income=Decimal("0"),
            capital_gains_income=Decimal("0"),
            other_sources_income=Decimal("0"),
            gross_total_income=Decimal("1200000"),
        ),
        deductions=DeductionBreakdown(
            claimed_total=Decimal("0"),
            allowed_total=Decimal("0"),
            disallowed_total=Decimal("0"),
            applied=[],
        ),
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
        warnings=warnings or [],
        steps=[],
    )


def generate_payload(validation_report=None, computation=None):
    return {
        "profile": sample_profile(),
        "candidate_itr": decision().model_dump(mode="json"),
        "validation_report": (validation_report or validation()).model_dump(mode="json"),
        "tax_computation_result": (computation or tax_result()).model_dump(mode="json"),
        "documents": [
            {
                "document_id": "doc-form16",
                "document_type": "form16",
                "original_filename": "form16.csv",
                "safe_filename": "form16.csv",
                "size": 128,
                "mime_type": "text/csv",
                "sha256": "a" * 64,
                "status": "extracted",
                "uploaded_at": "2026-05-30T00:00:00Z",
            }
        ],
    }


def test_clean_package_is_ready_for_ca_review_and_generates_artifacts():
    response = client.post("/v1/filing-packages/generate", json=generate_payload())

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ready_for_ca_review"
    assert payload["candidate_itr"] == "ITR-1"
    assert payload["readiness_score"] <= 90
    assert len(payload["artifacts"]) == 5
    assert any("Official ITR schema validation is not yet implemented" in warning["message"] for warning in payload["warnings"])


def test_validation_failed_blocks_package():
    response = client.post("/v1/filing-packages/generate", json=generate_payload(validation(ValidationStatus.FAILED, 20)))

    assert response.status_code == 200
    assert response.json()["status"] == FilingPackageStatus.BLOCKED


def test_needs_review_validation_and_tax_preview_keep_package_in_review():
    warning = TaxComputationWarning(code="VALIDATION_FAILED_PREVIEW", message="Validation failed; tax is preview only.")

    needs_review_response = client.post(
        "/v1/filing-packages/generate",
        json=generate_payload(validation(ValidationStatus.NEEDS_REVIEW, 70)),
    )
    preview_response = client.post(
        "/v1/filing-packages/generate",
        json=generate_payload(computation=tax_result(warnings=[warning], is_preview=True)),
    )

    assert needs_review_response.json()["status"] == "needs_review"
    assert preview_response.json()["status"] == "needs_review"


def test_draft_payload_is_internal_and_artifact_download_works():
    package = client.post("/v1/filing-packages/generate", json=generate_payload()).json()
    draft_artifact = next(item for item in package["artifacts"] if item["artifact_type"] == "draft_itr_payload")

    response = client.get(f"/v1/filing-packages/{package['package_id']}/artifacts/{draft_artifact['artifact_id']}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    draft_payload = response.json()
    assert draft_payload["payload_type"] == "draft_itr_payload"
    assert draft_payload["schema_status"] == "internal_draft_not_official"
    assert "Official ITR schema validation is not yet implemented" in str(draft_payload["warnings"])


def test_unknown_package_and_artifact_return_404():
    missing_package = client.get("/v1/filing-packages/33333333-3333-4333-8333-333333333333")
    package = client.post("/v1/filing-packages/generate", json=generate_payload()).json()
    missing_artifact = client.get(
        f"/v1/filing-packages/{package['package_id']}/artifacts/44444444-4444-4444-8444-444444444444"
    )

    assert missing_package.status_code == 404
    assert missing_artifact.status_code == 404


def test_package_response_and_artifacts_do_not_leak_sensitive_or_internal_values():
    package = client.post("/v1/filing-packages/generate", json=generate_payload()).json()

    response_text = str(package)
    assert "ABCDE1234F" not in response_text
    assert "123456789012" not in response_text
    assert "storage_path" not in response_text
    for artifact in package["artifacts"]:
        assert "ABCDE1234F" not in artifact["filename"]
        assert "123456789012" not in artifact["filename"]
        content = client.get(f"/v1/filing-packages/{package['package_id']}/artifacts/{artifact['artifact_id']}").text
        assert "ABCDE1234F" not in content
        assert "123456789012" not in content
        assert "storage_path" not in content


def test_explanation_is_grounded_and_never_claims_submission():
    package = client.post("/v1/filing-packages/generate", json=generate_payload()).json()

    response = client.post("/v1/filing-packages/explain", json={"package_id": package["package_id"]})

    assert response.status_code == 200
    explanation = response.json()["explanation"].lower()
    assert "draft filing package" in explanation
    assert "not submitted" in explanation
    assert "filed" not in explanation
    assert "accepted by government" not in explanation


def test_repository_stores_package_and_generation_does_not_mutate_profile():
    repository = FilingPackageRepository()
    service = FilingPackageService(repository=repository)
    profile = sample_profile()
    original = deepcopy(profile)

    package = service.generate(
        profile=profile,
        candidate_itr=decision(),
        validation_report=validation(),
        tax_computation_result=tax_result(),
        documents=[],
    )

    assert repository.get(package.package_id) == package
    assert profile == original


def test_filing_agent_delegates_only_to_package_service():
    class RecordingService:
        def __init__(self):
            self.called = False

        def generate(self, **kwargs):
            self.called = True
            return "package"

        def explain(self, package):
            return "explanation"

    service = RecordingService()
    agent = FilingAgent(service=service)

    result = agent.generate_package(
        profile=sample_profile(),
        candidate_itr=decision(),
        validation_report=validation(),
        tax_computation_result=tax_result(),
        documents=[],
    )

    assert result == "package"
    assert service.called is True

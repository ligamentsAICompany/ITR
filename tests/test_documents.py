from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.document import DocumentType, ExtractedField, ExtractionResult
from app.services.document_extraction_service import DocumentExtractionService
from app.services.document_validation_service import DocumentValidationService
from app.services.profile_merge_service import ProfileMergeService
from app.services.storage_service import LocalStorageService


client = TestClient(app)


def test_storage_sanitizes_filename_hashes_content_and_writes_metadata(tmp_path: Path):
    storage = LocalStorageService(tmp_path)

    record = storage.save(
        content=b"Gross Salary,1200000\n",
        original_filename="../Form 16 (FY25).csv",
        content_type="text/csv",
        document_type=DocumentType.FORM16,
    )

    assert record.safe_filename == "Form_16_FY25.csv"
    assert record.sha256
    assert record.size_bytes == 21
    assert record.storage_path.endswith("Form_16_FY25.csv")
    assert Path(record.storage_path).read_bytes() == b"Gross Salary,1200000\n"
    assert storage.get(record.document_id).sha256 == record.sha256


def test_document_validation_rejects_unsafe_extension_and_mime():
    validator = DocumentValidationService(max_size_bytes=1024)

    with pytest.raises(ValueError, match="Unsupported file type"):
        validator.validate(
            filename="payload.exe",
            content_type="application/octet-stream",
            size_bytes=5,
            document_type=DocumentType.AIS,
        )

    with pytest.raises(ValueError, match="does not match"):
        validator.validate(
            filename="statement.csv",
            content_type="application/pdf",
            size_bytes=5,
            document_type=DocumentType.BANK_STATEMENT,
        )


def test_csv_extraction_maps_conservative_tax_fields(tmp_path: Path):
    storage = LocalStorageService(tmp_path)
    record = storage.save(
        content=(
            b"Gross Salary,TDS,Interest Income,Section 80C\n"
            b"1200000,125000,4200,150000\n"
        ),
        original_filename="form16.csv",
        content_type="text/csv",
        document_type=DocumentType.FORM16,
    )

    result = DocumentExtractionService(storage).extract(record.document_id)

    fields_by_path = {field.raw_path: field for field in result.fields}
    assert result.status == "completed"
    assert fields_by_path["salaryIncome"].value == 1200000
    assert fields_by_path["tdsSalary"].value == 125000
    assert fields_by_path["otherSourcesInterest"].value == 4200
    assert fields_by_path["deduction80CAmount"].value == 150000
    assert all(field.source.document_id == record.document_id for field in result.fields)


def test_merge_applies_only_explicitly_approved_fields():
    extraction = ExtractionResult(
        document_id="doc-1",
        status="completed",
        fields=[
            ExtractedField(
                field_id="salary-1",
                label="Gross Salary",
                value=1200000,
                raw_path="salaryIncome",
                canonical_path="income_heads.salary.gross_amount",
                confidence=0.9,
                source={"document_id": "doc-1", "locator": "csv:Gross Salary"},
            ),
            ExtractedField(
                field_id="interest-1",
                label="Interest Income",
                value=4200,
                raw_path="otherSourcesInterest",
                canonical_path="income_heads.other_sources.interest_savings_amount",
                confidence=0.75,
                source={"document_id": "doc-1", "locator": "csv:Interest Income"},
            ),
        ],
    )

    result = ProfileMergeService().merge(
        current_payload={"salaryIncome": "0", "otherSourcesInterest": "0"},
        extraction_result=extraction,
        approved_field_ids=["interest-1"],
    )

    assert result.merged_payload == {"salaryIncome": "0", "otherSourcesInterest": "4200"}
    assert result.applied_field_ids == ["interest-1"]
    assert result.skipped_field_ids == ["salary-1"]


def test_upload_endpoint_accepts_multipart_and_extracts_csv(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))

    upload_response = client.post(
        "/v1/uploads",
        data={"document_type": "form16"},
        files={"file": ("form16.csv", b"Gross Salary\n1200000\n", "text/csv")},
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    assert upload_payload["original_filename"] == "form16.csv"
    assert upload_payload["sha256"]

    extract_response = client.post(f"/v1/uploads/{upload_payload['document_id']}/extract")

    assert extract_response.status_code == 200
    extract_payload = extract_response.json()
    assert extract_payload["status"] == "completed"
    assert extract_payload["fields"][0]["raw_path"] == "salaryIncome"


def test_merge_endpoint_requires_approved_fields():
    response = client.post(
        "/v1/intake/merge-extractions",
        json={
            "current_payload": {"salaryIncome": "0"},
            "approved_field_ids": [],
            "extraction_result": {
                "document_id": "doc-1",
                "status": "completed",
                "fields": [
                    {
                        "field_id": "salary-1",
                        "label": "Gross Salary",
                        "value": 1200000,
                        "raw_path": "salaryIncome",
                        "canonical_path": "income_heads.salary.gross_amount",
                        "confidence": 0.9,
                        "source": {"document_id": "doc-1", "locator": "csv:Gross Salary"},
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["merged_payload"] == {"salaryIncome": "0"}
    assert payload["applied_field_ids"] == []
    assert payload["skipped_field_ids"] == ["salary-1"]

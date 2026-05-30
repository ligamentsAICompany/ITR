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
    assert record.original_filename == "Form_16_FY25.csv"
    assert record.sha256
    assert record.size_bytes == 21
    assert record.storage_path.endswith("Form_16_FY25.csv")
    assert Path(record.storage_path).read_bytes() == b"Gross Salary,1200000\n"
    assert storage.get(record.document_id).sha256 == record.sha256


def test_storage_rejects_non_uuid_document_ids(tmp_path: Path):
    storage_root = tmp_path / "uploads"
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "metadata.json").write_text("{}", encoding="utf-8")
    storage = LocalStorageService(storage_root)

    with pytest.raises(FileNotFoundError):
        storage.get("../outside")


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
            b"PAN,Assessment Year,Previous Year,Gross Salary,Employer Name,TDS,Interest Income,"
            b"Section 80C,Section 80D,House Property Income,House Property Interest,"
            b"STCG Amount,LTCG 112A Amount,Other LTCG Amount\n"
            b"ABCDE1234F,2026-27,2025-26,1200000,Example Pvt Ltd,125000,4200,"
            b"150000,25000,180000,90000,30000,50000,12000\n"
        ),
        original_filename="form16.csv",
        content_type="text/csv",
        document_type=DocumentType.FORM16,
    )

    result = DocumentExtractionService(storage).extract(record.document_id)

    fields_by_path = {field.raw_path: field for field in result.fields}
    assert result.status == "completed"
    assert fields_by_path["pan"].value == "ABCDE1234F"
    assert fields_by_path["previousYear"].value == "2025-26"
    assert fields_by_path["salaryIncome"].value == 1200000
    assert fields_by_path["employerName"].value == "Example Pvt Ltd"
    assert fields_by_path["tdsSalary"].value == 125000
    assert fields_by_path["otherSourcesInterest"].value == 4200
    assert fields_by_path["deduction80CAmount"].value == 150000
    assert fields_by_path["deduction80DAmount"].value == 25000
    assert fields_by_path["housePropertyIncome"].value == 180000
    assert fields_by_path["housePropertyInterest"].value == 90000
    assert fields_by_path["stcgAmount"].value == 30000
    assert fields_by_path["ltcg112AAmount"].value == 50000
    assert fields_by_path["otherLtcgAmount"].value == 12000
    assert all(field.source.document_id == record.document_id for field in result.fields)


def test_pdf_decryption_failures_are_rejected(tmp_path: Path, monkeypatch):
    storage = LocalStorageService(tmp_path)
    record = storage.save(
        content=b"%PDF-1.4 encrypted placeholder",
        original_filename="locked.pdf",
        content_type="application/pdf",
        document_type=DocumentType.PDF_TEXT,
    )

    def raise_decrypt_error(_storage_path: str):
        raise Exception("file has not been decrypted")

    import pdfplumber

    monkeypatch.setattr(pdfplumber, "open", raise_decrypt_error)

    result = DocumentExtractionService(storage).extract(record.document_id)

    assert result.status == "rejected"
    assert result.warnings == ["Encrypted PDFs are not supported in Phase 1."]


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

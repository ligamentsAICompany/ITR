"""API endpoints for deterministic ITR classification."""

from os import getenv
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.decision import (
    ClarificationRequest,
    ClarificationResponse,
    ExplanationResponse,
    ITRDecisionResponse,
    MissingFieldsResponse,
)
from app.models.document import (
    DocumentType,
    ExtractionResult,
    MergeExtractionRequest,
    MergeExtractionResult,
    PublicDocumentMetadata,
)
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import (
    ValidationExplainRequest,
    ValidationExplainResponse,
    ValidationReport,
    ValidationRunRequest,
)
from app.agents.validation_agent import ValidationAgent
from app.core.config import get_settings
from app.services.document_extraction_service import DocumentExtractionService
from app.services.document_validation_service import DocumentValidationService
from app.services.explanation_service import explain_decision
from app.services.itr_service import get_missing_fields, run_itr_decision
from app.services.normalization_service import normalize_raw_user_data
from app.services.profile_merge_service import ProfileMergeService
from app.services.slm_service import get_default_slm_service
from app.services.storage_service import LocalStorageService

router = APIRouter()
VALIDATION_REPORTS: dict[str, ValidationReport] = {}


def _storage_service() -> LocalStorageService:
    return LocalStorageService(getenv("DOCUMENT_STORAGE_DIR", get_settings().document_storage_dir))


@router.post("/normalize", response_model=CanonicalTaxProfile)
def normalize(raw_user_data: dict[str, Any]) -> CanonicalTaxProfile:
    return normalize_raw_user_data(raw_user_data)


@router.post("/uploads", response_model=PublicDocumentMetadata)
async def upload_document(
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
) -> PublicDocumentMetadata:
    content = await file.read()
    try:
        DocumentValidationService(get_settings().max_upload_bytes).validate(
            filename=file.filename or "document",
            content_type=file.content_type or "application/octet-stream",
            size_bytes=len(content),
            document_type=document_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record = _storage_service().save(
        content=content,
        original_filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        document_type=document_type,
    )
    return record.to_public_metadata()


@router.get("/uploads/{document_id}", response_model=PublicDocumentMetadata)
def get_upload(document_id: str) -> PublicDocumentMetadata:
    try:
        return _storage_service().get(document_id).to_public_metadata()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.post("/uploads/{document_id}/extract", response_model=ExtractionResult)
def extract_upload(document_id: str) -> ExtractionResult:
    try:
        return DocumentExtractionService(_storage_service()).extract(document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.post("/intake/merge-extractions", response_model=MergeExtractionResult)
def merge_extractions(request: MergeExtractionRequest) -> MergeExtractionResult:
    return ProfileMergeService().merge(
        current_payload=request.current_payload,
        extraction_result=request.extraction_result,
        approved_field_ids=request.approved_field_ids,
    )


@router.post("/validation/run", response_model=ValidationReport)
def run_validation(request: ValidationRunRequest) -> ValidationReport:
    report = ValidationAgent().run(
        profile=request.profile,
        documents=request.documents,
        extractions=request.extractions,
        approved_field_ids=request.approved_field_ids,
        profile_id=request.profile_id,
        session_id=request.session_id,
    )
    VALIDATION_REPORTS[report.validation_run_id] = report
    return report


@router.get("/validation/{validation_run_id}", response_model=ValidationReport)
def get_validation_report(validation_run_id: str) -> ValidationReport:
    report = VALIDATION_REPORTS.get(validation_run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Validation report not found")
    return report


@router.post("/validation/explain", response_model=ValidationExplainResponse)
def explain_validation(request: ValidationExplainRequest) -> ValidationExplainResponse:
    report = VALIDATION_REPORTS.get(request.validation_run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Validation report not found")
    return ValidationAgent().explain(report)


@router.post("/itr-decision", response_model=ITRDecisionResponse)
def itr_decision(profile: CanonicalTaxProfile) -> ITRDecisionResponse:
    return run_itr_decision(profile)


@router.post("/missing-fields", response_model=MissingFieldsResponse)
def missing_fields(profile: CanonicalTaxProfile) -> MissingFieldsResponse:
    return get_missing_fields(profile)


@router.post("/explain", response_model=ExplanationResponse)
def explain(decision: ITRDecisionResponse) -> ExplanationResponse:
    return explain_decision(decision)


@router.post("/clarify", response_model=ClarificationResponse)
def clarify(request: ClarificationRequest) -> ClarificationResponse:
    slm_service = get_default_slm_service()
    question = slm_service.generate_clarification_question(
        missing_fields=request.missing_fields,
        context=request.context,
    )
    return ClarificationResponse(question=question)

"""API endpoints for deterministic ITR classification."""

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile

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
from app.models.filing_package import (
    FilingPackage,
    FilingPackageExplanation,
    FilingPackageExplainRequest,
    FilingPackageGenerateRequest,
)
from app.models.tax_profile import CanonicalTaxProfile
from app.models.tax_computation import (
    TaxComputeRequest,
    TaxComputationResult,
    TaxExplainRequest,
    TaxExplanationResponse,
)
from app.models.validation import (
    ValidationExplainRequest,
    ValidationExplainResponse,
    ValidationReport,
    ValidationRunRequest,
)
from app.agents.filing_agent import FilingAgent
from app.agents.tax_computation_agent import TaxComputationAgent
from app.agents.validation_agent import ValidationAgent
from app.core.auth import get_session_context
from app.core.config import get_settings
from app.models.auth import SessionContext
from app.services.audit_service import AuditService
from app.services.authorization_service import AuthorizationService
from app.repositories.filing_package_repository import FilingPackageRepository
from app.repositories.tax_computation_repository import TAX_COMPUTATION_CACHE, TaxComputationRepository
from app.repositories.validation_report_repository import VALIDATION_REPORT_CACHE, ValidationReportRepository
from app.services.document_extraction_service import DocumentExtractionService
from app.services.document_validation_service import DocumentValidationService
from app.services.explanation_service import explain_decision
from app.services.filing_package_service import FilingPackageService
from app.services.itr_service import get_missing_fields, run_itr_decision
from app.services.normalization_service import normalize_raw_user_data
from app.services.profile_merge_service import ProfileMergeService
from app.services.slm_service import get_default_slm_service
from app.services.storage_service import DocumentStorageService, get_document_storage_service
from app.services.tax_computation_service import MissingTaxConfigError

router = APIRouter()
# Non-production compatibility caches. Durable local persistence goes through repositories.
VALIDATION_REPORTS = VALIDATION_REPORT_CACHE
TAX_COMPUTATIONS = TAX_COMPUTATION_CACHE
validation_report_repository = ValidationReportRepository()
tax_computation_repository = TaxComputationRepository()
filing_package_repository = FilingPackageRepository()
authorization_service = AuthorizationService()
audit_service = AuditService()


def _storage_service() -> DocumentStorageService:
    return get_document_storage_service()


def _filing_package_service() -> FilingPackageService:
    return FilingPackageService(repository=filing_package_repository)


OWNER_EXCLUDE = {"owner_user_id", "organization_id", "created_by"}


def _deny(session: SessionContext, resource_type: str, resource_id: str, request: Request, reason: str) -> None:
    audit_service.record(
        event_type="access_denied",
        session=session,
        resource_type=resource_type,
        resource_id=resource_id,
        request=request,
        metadata_summary={"reason": reason},
    )
    raise HTTPException(status_code=403, detail="Access denied")


def _configuration_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=500, detail="Server persistence or storage backend is not configured for this mode")


@router.post("/normalize", response_model=CanonicalTaxProfile)
def normalize(raw_user_data: dict[str, Any]) -> CanonicalTaxProfile:
    return normalize_raw_user_data(raw_user_data)


@router.post("/uploads", response_model=PublicDocumentMetadata)
async def upload_document(
    request: Request,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    session: SessionContext = Depends(get_session_context),
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

    try:
        record = _storage_service().save(
            content=content,
            original_filename=file.filename or "document",
            content_type=file.content_type or "application/octet-stream",
            document_type=document_type,
            owner_user_id=session.user_id,
            organization_id=session.organization_id,
            created_by=session.user_id,
        )
    except (ValueError, RuntimeError) as exc:
        raise _configuration_error(exc) from exc
    audit_service.record(
        event_type="document_uploaded",
        session=session,
        resource_type="document",
        resource_id=record.document_id,
        request=request,
        metadata_summary={"document_type": document_type, "size_bytes": len(content)},
    )
    return record.to_public_metadata()


@router.get("/uploads/{document_id}", response_model=PublicDocumentMetadata)
def get_upload(
    document_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> PublicDocumentMetadata:
    try:
        record = _storage_service().get(document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    decision = authorization_service.can_read_document(session, record)
    if not decision.allowed:
        _deny(session, "document", document_id, request, decision.reason)
    return record.to_public_metadata()


@router.post("/uploads/{document_id}/extract", response_model=ExtractionResult, response_model_exclude=OWNER_EXCLUDE)
def extract_upload(
    document_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> ExtractionResult:
    try:
        storage = _storage_service()
        record = storage.get(document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    decision = authorization_service.can_write_document(session, record)
    if not decision.allowed:
        _deny(session, "document", document_id, request, decision.reason)
    result = DocumentExtractionService(storage).extract(document_id)
    audit_service.record(
        event_type="document_extracted",
        session=session,
        resource_type="document",
        resource_id=document_id,
        request=request,
        metadata_summary={"field_count": len(result.fields), "status": result.status},
    )
    return result


@router.post("/intake/merge-extractions", response_model=MergeExtractionResult)
def merge_extractions(
    payload: MergeExtractionRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> MergeExtractionResult:
    try:
        record = _storage_service().get(payload.extraction_result.document_id)
    except FileNotFoundError:
        record = None
    if record is not None:
        decision = authorization_service.can_write_document(session, record)
        if not decision.allowed:
            _deny(session, "document", payload.extraction_result.document_id, request, decision.reason)
    result = ProfileMergeService().merge(
        current_payload=payload.current_payload,
        extraction_result=payload.extraction_result,
        approved_field_ids=payload.approved_field_ids,
    )
    audit_service.record(
        event_type="extracted_value_accepted",
        session=session,
        resource_type="document",
        resource_id=payload.extraction_result.document_id,
        request=request,
        metadata_summary={"accepted_count": len(result.applied_field_ids)},
    )
    return result


@router.post("/validation/run", response_model=ValidationReport, response_model_exclude=OWNER_EXCLUDE)
def run_validation(
    payload: ValidationRunRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> ValidationReport:
    report = ValidationAgent().run(
        profile=payload.profile,
        documents=payload.documents,
        extractions=payload.extractions,
        approved_field_ids=payload.approved_field_ids,
        profile_id=payload.profile_id,
        session_id=payload.session_id,
    )
    report = report.model_copy(
        update={"owner_user_id": session.user_id, "organization_id": session.organization_id, "created_by": session.user_id}
    )
    try:
        saved = validation_report_repository.save(report)
    except (ValueError, NotImplementedError) as exc:
        raise _configuration_error(exc) from exc
    audit_service.record(
        event_type="validation_run",
        session=session,
        resource_type="validation_report",
        resource_id=saved.validation_run_id,
        request=request,
        metadata_summary={"status": saved.overall_status, "readiness_score": saved.readiness_score},
    )
    return saved


@router.get("/validation/{validation_run_id}", response_model=ValidationReport, response_model_exclude=OWNER_EXCLUDE)
def get_validation_report(
    validation_run_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> ValidationReport:
    report = validation_report_repository.get(validation_run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Validation report not found")
    decision = authorization_service.can_read_validation_report(session, report)
    if not decision.allowed:
        _deny(session, "validation_report", validation_run_id, request, decision.reason)
    return report


@router.post("/validation/explain", response_model=ValidationExplainResponse)
def explain_validation(
    payload: ValidationExplainRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> ValidationExplainResponse:
    report = validation_report_repository.get(payload.validation_run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Validation report not found")
    decision = authorization_service.can_read_validation_report(session, report)
    if not decision.allowed:
        _deny(session, "validation_report", payload.validation_run_id, request, decision.reason)
    response = ValidationAgent().explain(report)
    audit_service.record(
        event_type="explanation_generated",
        session=session,
        resource_type="validation_report",
        resource_id=payload.validation_run_id,
        request=request,
        metadata_summary={"kind": "validation"},
    )
    return response


@router.post("/tax/compute", response_model=TaxComputationResult, response_model_exclude=OWNER_EXCLUDE)
def compute_tax(
    payload: TaxComputeRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> TaxComputationResult:
    try:
        result = TaxComputationAgent().run(
            profile=payload.profile,
            candidate_itr=payload.candidate_itr,
            validation_report=payload.validation_report,
            selected_regime=payload.selected_regime,
        )
    except MissingTaxConfigError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "missing_tax_config", "message": str(exc)},
        ) from exc
    result = result.model_copy(
        update={"owner_user_id": session.user_id, "organization_id": session.organization_id, "created_by": session.user_id}
    )
    try:
        saved = tax_computation_repository.save(result)
    except (ValueError, NotImplementedError) as exc:
        raise _configuration_error(exc) from exc
    audit_service.record(
        event_type="tax_computation",
        session=session,
        resource_type="tax_computation",
        resource_id=saved.computation_id,
        request=request,
        metadata_summary={"candidate_itr": saved.candidate_itr, "is_preview": saved.is_preview},
    )
    return saved


@router.post("/tax/explain", response_model=TaxExplanationResponse)
def explain_tax(
    payload: TaxExplainRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> TaxExplanationResponse:
    result = tax_computation_repository.get(payload.computation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Tax computation not found")
    decision = authorization_service.can_read_tax_computation(session, result)
    if not decision.allowed:
        _deny(session, "tax_computation", payload.computation_id, request, decision.reason)
    response = TaxComputationAgent().explain(result)
    audit_service.record(
        event_type="explanation_generated",
        session=session,
        resource_type="tax_computation",
        resource_id=payload.computation_id,
        request=request,
        metadata_summary={"kind": "tax"},
    )
    return response


@router.get("/tax/{computation_id}", response_model=TaxComputationResult, response_model_exclude=OWNER_EXCLUDE)
def get_tax_computation(
    computation_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> TaxComputationResult:
    result = tax_computation_repository.get(computation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Tax computation not found")
    decision = authorization_service.can_read_tax_computation(session, result)
    if not decision.allowed:
        _deny(session, "tax_computation", computation_id, request, decision.reason)
    return result


@router.post("/filing-packages/generate", response_model=FilingPackage, response_model_exclude=OWNER_EXCLUDE)
def generate_filing_package(
    payload: FilingPackageGenerateRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingPackage:
    try:
        package = FilingAgent(service=_filing_package_service()).generate_package(
            profile=payload.profile,
            candidate_itr=payload.candidate_itr,
            validation_report=payload.validation_report,
            tax_computation_result=payload.tax_computation_result,
            documents=payload.documents,
            owner_user_id=session.user_id,
            organization_id=session.organization_id,
            created_by=session.user_id,
        )
    except (ValueError, NotImplementedError) as exc:
        raise _configuration_error(exc) from exc
    audit_service.record(
        event_type="filing_package_generated",
        session=session,
        resource_type="filing_package",
        resource_id=package.package_id,
        request=request,
        metadata_summary={"candidate_itr": package.candidate_itr, "status": package.status},
    )
    return package


@router.get("/filing-packages/{package_id}", response_model=FilingPackage, response_model_exclude=OWNER_EXCLUDE)
def get_filing_package(
    package_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingPackage:
    package = _filing_package_service().get(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Filing package not found")
    decision = authorization_service.can_read_filing_package(session, package)
    if not decision.allowed:
        _deny(session, "filing_package", package_id, request, decision.reason)
    return package


@router.get("/filing-packages/{package_id}/artifacts")
def list_filing_package_artifacts(
    package_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> list[dict[str, Any]]:
    package = _filing_package_service().get(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Filing package not found")
    decision = authorization_service.can_read_filing_package(session, package)
    if not decision.allowed:
        _deny(session, "filing_package", package_id, request, decision.reason)
    return [artifact.model_dump(mode="json") for artifact in package.artifacts]


@router.get("/filing-packages/{package_id}/artifacts/{artifact_id}")
def download_filing_package_artifact(
    package_id: str,
    artifact_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> Response:
    service = _filing_package_service()
    package = service.get(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Filing package not found")
    decision = authorization_service.can_download_artifact(session, package)
    if not decision.allowed:
        _deny(session, "filing_package_artifact", artifact_id, request, decision.reason)
    artifact = next((item for item in package.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Filing package artifact not found")
    content = service.get_artifact_content(package_id, artifact_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Filing package artifact not found")
    audit_service.record(
        event_type="artifact_downloaded",
        session=session,
        resource_type="filing_package_artifact",
        resource_id=artifact_id,
        request=request,
        metadata_summary={"package_id": package_id, "artifact_type": artifact.artifact_type},
    )
    return Response(
        content=content,
        media_type=artifact.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )


@router.post("/filing-packages/explain", response_model=FilingPackageExplanation)
def explain_filing_package(
    payload: FilingPackageExplainRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingPackageExplanation:
    service = _filing_package_service()
    package = service.get(payload.package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Filing package not found")
    decision = authorization_service.can_read_filing_package(session, package)
    if not decision.allowed:
        _deny(session, "filing_package", payload.package_id, request, decision.reason)
    response = FilingAgent(service=service).explain(package)
    audit_service.record(
        event_type="explanation_generated",
        session=session,
        resource_type="filing_package",
        resource_id=payload.package_id,
        request=request,
        metadata_summary={"kind": "filing_package"},
    )
    return response


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

"""API endpoints for deterministic ITR classification."""

import hashlib
import hmac
import json
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
from app.models.filing_approval import FilingApproval, FilingApprovalAction, FilingApprovalRequest
from app.models.filing_consent import FilingConsent, FilingConsentAction, FilingConsentRequest, hash_optional
from app.models.filing_submission import (
    Acknowledgement,
    FilingExplainRequest,
    FilingExplanation,
    FilingSubmission,
    FilingSubmissionRequest,
)
from app.models.audit import AuditEvent
from app.models.provider_integration import ProviderCallbackEvent
from app.models.itr_export import (
    ItrExport,
    ItrExportExplainRequest,
    ItrExportExplanation,
    ItrExportGenerateRequest,
    ItrExportValidateRequest,
    OfficialSchemaValidationResult,
)
from app.models.schema_pack import SchemaPack
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
from app.agents.government_filing_agent import GovernmentFilingAgent
from app.agents.itr_export_agent import ItrExportAgent
from app.agents.tax_computation_agent import TaxComputationAgent
from app.agents.validation_agent import ValidationAgent
from app.core.auth import get_session_context
from app.core.config import get_settings
from app.models.auth import SessionContext
from app.services.audit_service import AuditService
from app.services.authorization_service import AuthorizationService
from app.repositories.filing_package_repository import FilingPackageRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.filing_workflow_repository import FilingSubmissionRepository
from app.repositories.itr_export_repository import ItrExportRepository
from app.repositories.schema_pack_repository import SchemaPackRepository
from app.repositories.tax_computation_repository import TAX_COMPUTATION_CACHE, TaxComputationRepository
from app.repositories.validation_report_repository import VALIDATION_REPORT_CACHE, ValidationReportRepository
from app.services.document_extraction_service import DocumentExtractionService
from app.services.document_validation_service import DocumentValidationService
from app.services.explanation_service import explain_decision
from app.services.filing_package_service import FilingPackageService
from app.services.filing_readiness_service import FilingReadinessResult
from app.services.filing_service import FilingService
from app.services.eri_provider import normalize_provider_status
from app.services.itr_export_service import ItrExportService
from app.services.itr_service import get_missing_fields, run_itr_decision
from app.services.normalization_service import normalize_raw_user_data
from app.services.profile_merge_service import ProfileMergeService
from app.services.slm_service import get_default_slm_service
from app.services.storage_service import DocumentStorageService, get_document_storage_service
from app.services.tax_computation_service import MissingTaxConfigError
from app.services.schema_pack_service import SchemaPackService
from app.models.auth import UserRole

router = APIRouter()
# Non-production compatibility caches. Durable local persistence goes through repositories.
VALIDATION_REPORTS = VALIDATION_REPORT_CACHE
TAX_COMPUTATIONS = TAX_COMPUTATION_CACHE
validation_report_repository = ValidationReportRepository()
tax_computation_repository = TaxComputationRepository()
filing_package_repository = FilingPackageRepository()
schema_pack_repository = SchemaPackRepository()
itr_export_repository = ItrExportRepository()
authorization_service = AuthorizationService()
audit_service = AuditService()
provider_callback_audit_repository = AuditRepository()
provider_callback_submission_repository = FilingSubmissionRepository()


def _storage_service() -> DocumentStorageService:
    return get_document_storage_service()


def _filing_package_service() -> FilingPackageService:
    return FilingPackageService(repository=filing_package_repository)


def _schema_pack_service() -> SchemaPackService:
    return SchemaPackService(repository=schema_pack_repository)


def _itr_export_service() -> ItrExportService:
    return ItrExportService(repository=itr_export_repository, schema_pack_service=_schema_pack_service())


def _filing_service() -> FilingService:
    return FilingService(
        package_repository=filing_package_repository,
        export_repository=itr_export_repository,
        authorization_service=authorization_service,
    )


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


def _require_admin(session: SessionContext) -> None:
    if session.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/schema-packs/upload", response_model=SchemaPack)
async def upload_schema_pack(
    request: Request,
    file: UploadFile = File(...),
    assessment_year: str | None = Form(default=None),
    previous_year: str | None = Form(default=None),
    itr_form: str | None = Form(default=None),
    schema_version: str | None = Form(default=None),
    session: SessionContext = Depends(get_session_context),
) -> SchemaPack:
    _require_admin(session)
    content = await file.read()
    try:
        schema_pack = _schema_pack_service().upload(
            filename=file.filename or "schema.json",
            content=content,
            assessment_year=assessment_year,
            previous_year=previous_year,
            itr_form=itr_form,
            schema_version=schema_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_service.record(
        event_type="schema_pack_uploaded",
        session=session,
        resource_type="schema_pack",
        resource_id=schema_pack.schema_pack_id,
        request=request,
        metadata_summary={
            "assessment_year": schema_pack.assessment_year,
            "itr_form": schema_pack.itr_form,
            "schema_version": schema_pack.schema_version,
        },
    )
    return schema_pack


@router.get("/schema-packs", response_model=list[SchemaPack])
def list_schema_packs(
    session: SessionContext = Depends(get_session_context),
) -> list[SchemaPack]:
    _require_admin(session)
    return _schema_pack_service().list()


@router.get("/schema-packs/{schema_pack_id}", response_model=SchemaPack)
def get_schema_pack(
    schema_pack_id: str,
    session: SessionContext = Depends(get_session_context),
) -> SchemaPack:
    _require_admin(session)
    schema_pack = _schema_pack_service().get(schema_pack_id)
    if schema_pack is None:
        raise HTTPException(status_code=404, detail="Schema pack not found")
    return schema_pack


@router.post("/schema-packs/{schema_pack_id}/activate", response_model=SchemaPack)
def activate_schema_pack(
    schema_pack_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> SchemaPack:
    _require_admin(session)
    try:
        schema_pack = _schema_pack_service().activate(schema_pack_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if schema_pack is None:
        raise HTTPException(status_code=404, detail="Schema pack not found")
    audit_service.record(
        event_type="schema_pack_activated",
        session=session,
        resource_type="schema_pack",
        resource_id=schema_pack.schema_pack_id,
        request=request,
        metadata_summary={"assessment_year": schema_pack.assessment_year, "itr_form": schema_pack.itr_form},
    )
    return schema_pack


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


@router.post("/itr-exports/generate", response_model=ItrExport, response_model_exclude=OWNER_EXCLUDE)
def generate_itr_export(
    payload: ItrExportGenerateRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> ItrExport:
    package = None
    if payload.package_id:
        package = _filing_package_service().get(payload.package_id)
        if package is None:
            raise HTTPException(status_code=404, detail="Filing package not found")
        decision = authorization_service.can_read_filing_package(session, package)
        if not decision.allowed:
            _deny(session, "filing_package", payload.package_id, request, decision.reason)
    if not (payload.profile and payload.candidate_itr and payload.validation_report and payload.tax_computation_result):
        raise HTTPException(status_code=422, detail="Profile, ITR decision, validation report, and tax computation are required")
    export = ItrExportAgent(service=_itr_export_service()).generate_export(
        profile=payload.profile,
        candidate_itr=payload.candidate_itr,
        validation_report=payload.validation_report,
        tax_computation_result=payload.tax_computation_result,
        package=package,
        owner_user_id=session.user_id,
        organization_id=session.organization_id,
        created_by=session.user_id,
    )
    audit_service.record(
        event_type="itr_export_generated",
        session=session,
        resource_type="itr_export",
        resource_id=export.export_id,
        request=request,
        metadata_summary={"candidate_itr": export.candidate_itr, "status": export.status},
    )
    if export.status in {"blocked", "schema_failed", "not_configured"}:
        audit_service.record(
            event_type="itr_export_validation_failed",
            session=session,
            resource_type="itr_export",
            resource_id=export.export_id,
            request=request,
            metadata_summary={"status": export.status, "error_count": len(export.validation_result.errors)},
        )
    return export


@router.get("/itr-exports/{export_id}", response_model=ItrExport, response_model_exclude=OWNER_EXCLUDE)
def get_itr_export(
    export_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> ItrExport:
    export = _itr_export_service().get(export_id)
    if export is None:
        raise HTTPException(status_code=404, detail="ITR export not found")
    decision = authorization_service.can_read_filing_package(session, export)
    if not decision.allowed:
        _deny(session, "itr_export", export_id, request, decision.reason)
    return export


@router.get("/itr-exports/{export_id}/artifacts")
def list_itr_export_artifacts(
    export_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> list[dict[str, Any]]:
    export = _itr_export_service().get(export_id)
    if export is None:
        raise HTTPException(status_code=404, detail="ITR export not found")
    decision = authorization_service.can_download_artifact(session, export)
    if not decision.allowed:
        _deny(session, "itr_export_artifact", export_id, request, decision.reason)
    return [artifact.model_dump(mode="json") for artifact in export.artifacts]


@router.get("/itr-exports/{export_id}/artifacts/{artifact_id}")
def download_itr_export_artifact(
    export_id: str,
    artifact_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> Response:
    service = _itr_export_service()
    export = service.get(export_id)
    if export is None:
        raise HTTPException(status_code=404, detail="ITR export not found")
    decision = authorization_service.can_download_artifact(session, export)
    if not decision.allowed:
        _deny(session, "itr_export_artifact", artifact_id, request, decision.reason)
    artifact = next((item for item in export.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None:
        raise HTTPException(status_code=404, detail="ITR export artifact not found")
    content = service.get_artifact_content(export_id, artifact_id)
    if content is None:
        raise HTTPException(status_code=404, detail="ITR export artifact not found")
    audit_service.record(
        event_type="itr_export_downloaded",
        session=session,
        resource_type="itr_export_artifact",
        resource_id=artifact_id,
        request=request,
        metadata_summary={"export_id": export_id, "artifact_type": artifact.artifact_type},
    )
    return Response(
        content=content,
        media_type=artifact.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )


@router.post("/itr-exports/validate", response_model=OfficialSchemaValidationResult)
def validate_itr_export(
    payload: ItrExportValidateRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> OfficialSchemaValidationResult:
    result = _itr_export_service().validate_only(
        profile=payload.profile,
        candidate_itr=payload.candidate_itr,
        validation_report=payload.validation_report,
        tax_computation_result=payload.tax_computation_result,
    )
    audit_service.record(
        event_type="itr_export_validation_run",
        session=session,
        resource_type="itr_export_validation",
        resource_id=result.validation_id,
        request=request,
        metadata_summary={"candidate_itr": result.candidate_itr, "status": result.status},
    )
    return result


@router.post("/itr-exports/explain", response_model=ItrExportExplanation)
def explain_itr_export(
    payload: ItrExportExplainRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> ItrExportExplanation:
    service = _itr_export_service()
    export = service.get(payload.export_id)
    if export is None:
        raise HTTPException(status_code=404, detail="ITR export not found")
    decision = authorization_service.can_read_filing_package(session, export)
    if not decision.allowed:
        _deny(session, "itr_export", payload.export_id, request, decision.reason)
    response = ItrExportAgent(service=service).explain(export)
    audit_service.record(
        event_type="explanation_generated",
        session=session,
        resource_type="itr_export",
        resource_id=payload.export_id,
        request=request,
        metadata_summary={"kind": "itr_export"},
    )
    return response


def _filing_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail="Access denied")
    return HTTPException(status_code=400, detail=str(exc))


def _verify_provider_callback_signature(*, body: bytes, signature: str | None) -> bool:
    settings = get_settings()
    secret = settings.eri_client_secret
    if not secret:
        return not settings.is_production or settings.allow_unsigned_provider_callbacks
    if not signature:
        return False
    supplied = signature.removeprefix("sha256=").strip()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


def _audit_provider_callback(event: ProviderCallbackEvent) -> None:
    submission = provider_callback_submission_repository.get_by_provider_reference(event.provider_reference_id)
    actor = submission.created_by or submission.owner_user_id if submission is not None else "00000000-0000-4000-8000-000000000000"
    org = submission.organization_id if submission is not None else "00000000-0000-4000-8000-000000000000"
    provider_callback_audit_repository.save(
        AuditEvent(
            event_type="provider_callback_received",
            actor_user_id=actor or "00000000-0000-4000-8000-000000000000",
            organization_id=org or "00000000-0000-4000-8000-000000000000",
            resource_type="filing_submission",
            resource_id=submission.submission_id if submission is not None else event.provider_reference_id,
            request_id=event.callback_id,
            metadata_summary={
                "provider": event.provider,
                "event_type": event.event_type,
                "verified": event.verified,
                "provider_status": event.provider_status,
                "normalized_status": event.normalized_status,
            },
        )
    )


@router.post("/filing/provider-callbacks/{provider}", response_model=ProviderCallbackEvent)
async def provider_callback(provider: str, request: Request) -> ProviderCallbackEvent:
    body = await request.body()
    verified = _verify_provider_callback_signature(body=body, signature=request.headers.get("X-Provider-Signature"))
    settings = get_settings()
    if settings.is_production and not verified and not settings.allow_unsigned_provider_callbacks:
        raise HTTPException(status_code=401, detail="Provider callback signature verification failed")
    try:
        payload = json.loads(body.decode() or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Provider callback payload is invalid") from exc
    provider_status = str(payload.get("provider_status") or payload.get("status") or "status_unknown")
    event = ProviderCallbackEvent(
        callback_id=str(payload.get("callback_id") or payload.get("event_id") or "00000000-0000-4000-8000-000000000000"),
        provider=provider,
        event_type=str(payload.get("event_type") or "status_update"),
        provider_reference_id=str(payload.get("provider_reference_id") or ""),
        verified=verified,
        provider_status=provider_status,
        normalized_status=normalize_provider_status(provider_status),
    )
    submission = provider_callback_submission_repository.get_by_provider_reference(event.provider_reference_id)
    if submission is not None and event.normalized_status is not None:
        submission.submission_status = event.normalized_status
        submission.last_checked_at = event.received_at
        submission.updated_at = event.received_at
        provider_callback_submission_repository.save(submission)
    _audit_provider_callback(event)
    return event


@router.post("/filing/consents/request", response_model=FilingConsent)
def request_filing_consent(
    payload: FilingConsentRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingConsent:
    try:
        consent = _filing_service().request_consent(
            package_id=payload.package_id,
            export_id=payload.export_id,
            consent_text=payload.consent_text,
            session=session,
            ip_hash=hash_optional(request.client.host if request.client else None),
            user_agent_hash=hash_optional(request.headers.get("user-agent")),
        )
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_consent_requested",
        session=session,
        resource_type="filing_consent",
        resource_id=consent.consent_id,
        request=request,
        metadata_summary={"package_id": consent.package_id, "export_id": consent.export_id},
    )
    return consent


@router.post("/filing/consents/{consent_id}/grant", response_model=FilingConsent)
def grant_filing_consent(
    consent_id: str,
    _payload: FilingConsentAction,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingConsent:
    try:
        consent = _filing_service().grant_consent(consent_id=consent_id, session=session)
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_consent_granted",
        session=session,
        resource_type="filing_consent",
        resource_id=consent.consent_id,
        request=request,
        metadata_summary={"package_id": consent.package_id, "export_id": consent.export_id},
    )
    return consent


@router.post("/filing/consents/{consent_id}/revoke", response_model=FilingConsent)
def revoke_filing_consent(
    consent_id: str,
    _payload: FilingConsentAction,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingConsent:
    try:
        consent = _filing_service().revoke_consent(consent_id=consent_id, session=session)
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_consent_revoked",
        session=session,
        resource_type="filing_consent",
        resource_id=consent.consent_id,
        request=request,
        metadata_summary={"package_id": consent.package_id, "export_id": consent.export_id},
    )
    return consent


@router.post("/filing/approvals/request", response_model=FilingApproval)
def request_filing_approval(
    payload: FilingApprovalRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingApproval:
    try:
        approval = _filing_service().request_approval(
            package_id=payload.package_id,
            export_id=payload.export_id,
            approval_notes=payload.approval_notes,
            session=session,
        )
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_approval_requested",
        session=session,
        resource_type="filing_approval",
        resource_id=approval.approval_id,
        request=request,
        metadata_summary={"package_id": approval.package_id, "export_id": approval.export_id},
    )
    return approval


@router.post("/filing/approvals/{approval_id}/approve", response_model=FilingApproval)
def approve_filing(
    approval_id: str,
    payload: FilingApprovalAction,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingApproval:
    try:
        approval = _filing_service().approve(
            approval_id=approval_id,
            session=session,
            approval_notes=payload.approval_notes,
        )
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_approval_approved",
        session=session,
        resource_type="filing_approval",
        resource_id=approval.approval_id,
        request=request,
        metadata_summary={"package_id": approval.package_id, "export_id": approval.export_id},
    )
    return approval


@router.post("/filing/approvals/{approval_id}/reject", response_model=FilingApproval)
def reject_filing(
    approval_id: str,
    payload: FilingApprovalAction,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingApproval:
    try:
        approval = _filing_service().reject(
            approval_id=approval_id,
            session=session,
            approval_notes=payload.approval_notes,
        )
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_approval_rejected",
        session=session,
        resource_type="filing_approval",
        resource_id=approval.approval_id,
        request=request,
        metadata_summary={"package_id": approval.package_id, "export_id": approval.export_id},
    )
    return approval


@router.post("/filing/submissions", response_model=FilingSubmission, response_model_exclude=OWNER_EXCLUDE)
def create_filing_submission(
    payload: FilingSubmissionRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingSubmission:
    try:
        submission = _filing_service().create_draft(
            package_id=payload.package_id,
            export_id=payload.export_id,
            session=session,
        )
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_submission_draft_created",
        session=session,
        resource_type="filing_submission",
        resource_id=submission.submission_id,
        request=request,
        metadata_summary={"provider_mode": submission.provider_mode},
    )
    return submission


@router.post("/filing/submissions/{submission_id}/readiness", response_model=FilingReadinessResult)
def filing_submission_readiness(
    submission_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingReadinessResult:
    try:
        result = _filing_service().readiness(submission_id=submission_id, session=session)
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_readiness_checked",
        session=session,
        resource_type="filing_submission",
        resource_id=submission_id,
        request=request,
        metadata_summary={"ready": result.ready, "provider_mode": result.provider_mode},
    )
    return result


@router.post("/filing/submissions/{submission_id}/submit", response_model=FilingSubmission, response_model_exclude=OWNER_EXCLUDE)
def submit_filing_submission(
    submission_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingSubmission:
    try:
        submission = _filing_service().submit(submission_id=submission_id, session=session)
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_submission_submitted",
        session=session,
        resource_type="filing_submission",
        resource_id=submission.submission_id,
        request=request,
        metadata_summary={"provider_mode": submission.provider_mode, "status": submission.submission_status},
    )
    return submission


@router.get("/filing/submissions/{submission_id}", response_model=FilingSubmission, response_model_exclude=OWNER_EXCLUDE)
def get_filing_submission(
    submission_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingSubmission:
    try:
        return _filing_service().get_submission(submission_id=submission_id, session=session)
    except Exception as exc:
        raise _filing_error(exc) from exc


@router.post("/filing/submissions/{submission_id}/status-check", response_model=FilingSubmission, response_model_exclude=OWNER_EXCLUDE)
def check_filing_submission_status(
    submission_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingSubmission:
    try:
        submission = _filing_service().check_status(submission_id=submission_id, session=session)
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_status_checked",
        session=session,
        resource_type="filing_submission",
        resource_id=submission.submission_id,
        request=request,
        metadata_summary={"status": submission.submission_status},
    )
    return submission


@router.post("/filing/submissions/{submission_id}/everification/initiate", response_model=FilingSubmission, response_model_exclude=OWNER_EXCLUDE)
def initiate_everification(
    submission_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingSubmission:
    try:
        submission = _filing_service().initiate_everification(submission_id=submission_id, session=session)
    except Exception as exc:
        raise _filing_error(exc) from exc
    audit_service.record(
        event_type="filing_everification_initiated",
        session=session,
        resource_type="filing_submission",
        resource_id=submission.submission_id,
        request=request,
        metadata_summary={"everification_status": submission.everification_status},
    )
    return submission


@router.get("/filing/submissions/{submission_id}/everification", response_model=FilingSubmission, response_model_exclude=OWNER_EXCLUDE)
def get_everification_status(
    submission_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingSubmission:
    try:
        return _filing_service().everification_status(submission_id=submission_id, session=session)
    except Exception as exc:
        raise _filing_error(exc) from exc


@router.get("/filing/submissions/{submission_id}/acknowledgement", response_model=Acknowledgement)
def get_acknowledgement(
    submission_id: str,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> Acknowledgement:
    try:
        return _filing_service().acknowledgement(submission_id=submission_id, session=session)
    except Exception as exc:
        raise _filing_error(exc) from exc


@router.post("/filing/explain", response_model=FilingExplanation)
def explain_government_filing(
    payload: FilingExplainRequest,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> FilingExplanation:
    try:
        _filing_service().get_submission(submission_id=payload.submission_id, session=session)
    except Exception as exc:
        raise _filing_error(exc) from exc
    explanation = GovernmentFilingAgent().explain_submission(payload.submission_id, session_user_id=session.user_id)
    audit_service.record(
        event_type="filing_explanation_generated",
        session=session,
        resource_type="filing_submission",
        resource_id=payload.submission_id,
        request=request,
        metadata_summary={"kind": "filing"},
    )
    return explanation


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

"""Deterministic readiness checks before any filing-provider submission."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.auth import SessionContext
from app.models.filing_package import FilingPackageStatus
from app.models.itr_export import ItrExportStatus, OfficialSchemaValidationStatus
from app.repositories.filing_package_repository import FilingPackageRepository
from app.repositories.filing_workflow_repository import FilingApprovalRepository, FilingConsentRepository
from app.repositories.itr_export_repository import ItrExportRepository
from app.services.authorization_service import AuthorizationService
from app.services.filing_provider_factory import get_filing_provider_configuration


class FilingReadinessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    provider: str = "mock"
    provider_mode: str = "mock"


class FilingReadinessService:
    def __init__(
        self,
        *,
        package_repository: FilingPackageRepository | None = None,
        export_repository: ItrExportRepository | None = None,
        consent_repository: FilingConsentRepository | None = None,
        approval_repository: FilingApprovalRepository | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        self.package_repository = package_repository or FilingPackageRepository()
        self.export_repository = export_repository or ItrExportRepository()
        self.consent_repository = consent_repository or FilingConsentRepository()
        self.approval_repository = approval_repository or FilingApprovalRepository()
        self.authorization_service = authorization_service or AuthorizationService()

    def check(self, *, package_id: str, export_id: str, session: SessionContext) -> FilingReadinessResult:
        blockers: list[str] = []
        warnings: list[str] = []
        required_actions: list[str] = []
        provider_config = get_filing_provider_configuration()

        package = self.package_repository.get(package_id)
        export = self.export_repository.get(export_id)
        if package is None:
            blockers.append("filing_package_missing")
        if export is None:
            blockers.append("export_missing")
        if package is not None and not self.authorization_service.can_read_filing_package(session, package).allowed:
            blockers.append("access_denied")
        if export is not None and not self.authorization_service.can_read_filing_package(session, export).allowed:
            blockers.append("access_denied")
        if package is not None and export is not None and export.package_id != package.package_id:
            blockers.append("package_export_mismatch")
        if package is not None and not package.computation_id:
            blockers.append("tax_computation_missing")
        if package is not None and package.status == FilingPackageStatus.BLOCKED:
            blockers.append("filing_package_blocked")
        if export is not None and export.status != ItrExportStatus.READY_FOR_DOWNLOAD:
            blockers.append("export_not_ready")
        if export is not None and (
            export.status == ItrExportStatus.SCHEMA_FAILED
            or export.validation_result.status == OfficialSchemaValidationStatus.FAILED
        ):
            blockers.append("schema_validation_failed")

        if package is not None and export is not None:
            consent = self.consent_repository.active_for(
                package_id=package.package_id,
                export_id=export.export_id,
                user_id=package.owner_user_id or session.user_id,
                organization_id=package.organization_id or session.organization_id,
            )
            if consent is None:
                blockers.append("missing_consent")
                required_actions.append("Request and grant taxpayer consent for this package/export pair.")
            approval = self.approval_repository.approved_for(
                package_id=package.package_id,
                export_id=export.export_id,
                organization_id=package.organization_id or session.organization_id,
            )
            if approval is None:
                blockers.append("approval_pending")
                required_actions.append("Obtain reviewer or admin approval before filing submission.")

        if not provider_config.configured:
            if provider_config.provider_mode == "live" and not provider_config.live_allowed:
                blockers.append("live_filing_disabled")
            else:
                blockers.append("provider_not_configured")
        if provider_config.provider_mode in {"mock", "sandbox"}:
            warnings.append("This is a mock/sandbox filing workflow for testing. It does not file a real tax return.")

        return FilingReadinessResult(
            ready=not blockers,
            blockers=sorted(set(blockers)),
            warnings=warnings,
            required_actions=required_actions,
            provider=provider_config.provider,
            provider_mode=provider_config.provider_mode,
        )

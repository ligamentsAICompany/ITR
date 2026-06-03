"""Privacy-safe provider diagnostics and observability."""

import logging
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.models.provider_integration import ProviderCapability, ProviderMode
from app.repositories.provider_spec_repository import ProviderContractResultRepository, ProviderSpecRepository
from app.services.pilot_readiness_service import PilotReadinessService
from app.services.provider_credentials_service import ProviderCredentialsService
from app.services.provider_spec_service import ProviderSpecService
from app.services.secret_verification_service import SecretVerificationService

logger = logging.getLogger(__name__)


class ProviderDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    mode: str
    configured: bool
    live_filing_enabled: bool
    secret_backend: str
    sandbox_configured: bool
    sandbox_secrets_verified: bool
    sandbox_spec_active: bool
    sandbox_calls_allowed: bool
    sandbox_contract_status: str
    sandbox_smoke_status: str
    last_sandbox_contract_test_at: datetime | None = None
    last_sandbox_smoke_at: datetime | None = None
    pilot_ready: bool
    pilot_blockers: list[str] = Field(default_factory=list)
    pilot_warnings: list[str] = Field(default_factory=list)
    pilot_verified_items: list[str] = Field(default_factory=list)
    pilot_not_verified_items: list[str] = Field(default_factory=list)
    live_configured: bool
    live_enabled: bool
    live_blocked_reason: str | None = None
    provider_capabilities: list[str] = Field(default_factory=list)
    safe_missing_config: list[str] = Field(default_factory=list)
    supported_operations: list[str] = Field(default_factory=list)
    status: str
    safe_readiness: str
    safe_error: str | None = None
    last_contract_test: dict = Field(default_factory=dict)
    retryable_provider_error: str | None = None
    last_status_check: datetime | None = None


class ProviderObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    mode: str
    operation: str
    status: str
    duration_ms: int
    retry_count: int
    error_code: str | None = None
    normalized_status: str | None = None
    request_id: str | None = None
    submission_id: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProviderDiagnosticsService:
    def __init__(
        self,
        *,
        spec_repository: ProviderSpecRepository | None = None,
        result_repository: ProviderContractResultRepository | None = None,
    ) -> None:
        self.spec_repository = spec_repository or ProviderSpecRepository()
        self.result_repository = result_repository or ProviderContractResultRepository()
        self.spec_service = ProviderSpecService(repository=self.spec_repository)

    def current(self) -> ProviderDiagnostics:
        settings = get_settings()
        try:
            readiness = self.spec_service.readiness_for_current_provider()
            contract_provider = "mock" if readiness.provider == "mock" else "eri"
            last_contract = self.result_repository.latest(provider=contract_provider, mode=readiness.mode) or {}
            sandbox_contract = self.result_repository.latest(provider="eri", mode="sandbox") or {}
            sandbox_smoke = self.result_repository.latest(provider="eri", mode="sandbox_smoke") or {}
            sandbox_spec = self.spec_repository.get_active(provider_name="eri", provider_mode=ProviderMode.SANDBOX)
            sandbox_secrets_verified = SecretVerificationService().verify_sandbox().verified
            sandbox_configured = sandbox_spec is not None and sandbox_secrets_verified
            pilot_report = PilotReadinessService(spec_repository=self.spec_repository, result_repository=self.result_repository).generate()
            live_spec = self.spec_repository.get_active(provider_name="eri", provider_mode=ProviderMode.LIVE)
            live_credentials = ProviderCredentialsService().load(mode=ProviderMode.LIVE)
            live_configured = live_spec is not None and live_credentials.configured and settings.live_filing_approval_complete
            live_enabled = live_configured and settings.allow_live_filing and settings.environment == "production"
            live_blocked_reason = None
            if not live_enabled:
                if not settings.allow_live_filing:
                    live_blocked_reason = "Live filing is disabled by default."
                elif not settings.live_filing_approval_complete:
                    live_blocked_reason = "Live filing approval metadata is required before live filing can be enabled."
                elif settings.environment != "production":
                    live_blocked_reason = "Live filing requires ENVIRONMENT=production."
                elif not live_configured:
                    live_blocked_reason = "Live provider configuration is incomplete."
            capabilities = list(readiness.supported_operations)
            return ProviderDiagnostics(
                provider=readiness.provider,
                mode=readiness.mode,
                configured=readiness.configured,
                live_filing_enabled=live_enabled and readiness.mode == "live" and readiness.configured,
                secret_backend=settings.secret_backend,
                sandbox_configured=sandbox_configured,
                sandbox_secrets_verified=sandbox_secrets_verified,
                sandbox_spec_active=sandbox_spec is not None,
                sandbox_calls_allowed=settings.allow_sandbox_provider_calls,
                sandbox_contract_status=str(sandbox_contract.get("status") or "not_verified"),
                sandbox_smoke_status=str(sandbox_smoke.get("status") or "not_verified"),
                last_sandbox_contract_test_at=_parse_datetime(sandbox_contract.get("tested_at")),
                last_sandbox_smoke_at=_parse_datetime(sandbox_smoke.get("tested_at")),
                pilot_ready=pilot_report.pilot_ready,
                pilot_blockers=pilot_report.blockers,
                pilot_warnings=pilot_report.warnings,
                pilot_verified_items=pilot_report.verified_items,
                pilot_not_verified_items=pilot_report.not_verified_items,
                live_configured=live_configured,
                live_enabled=live_enabled,
                live_blocked_reason=live_blocked_reason,
                provider_capabilities=capabilities,
                safe_missing_config=list(readiness.missing),
                supported_operations=capabilities,
                status=readiness.status,
                safe_readiness=readiness.status,
                safe_error=readiness.safe_error,
                last_contract_test=last_contract,
            )
        except Exception:
            if settings.environment != "demo":
                raise
            logger.exception("Demo provider diagnostics failed; returning safe degraded diagnostics")
            return _demo_fallback_diagnostics(settings)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _demo_fallback_diagnostics(settings) -> ProviderDiagnostics:
    capabilities = [item.value for item in ProviderCapability]
    return ProviderDiagnostics(
        provider=settings.filing_provider,
        mode=settings.filing_provider_mode,
        configured=settings.filing_provider == "mock",
        live_filing_enabled=False,
        secret_backend=settings.secret_backend,
        sandbox_configured=False,
        sandbox_secrets_verified=False,
        sandbox_spec_active=False,
        sandbox_calls_allowed=settings.allow_sandbox_provider_calls,
        sandbox_contract_status="not_verified",
        sandbox_smoke_status="not_verified",
        pilot_ready=False,
        pilot_blockers=[],
        pilot_warnings=["Demo diagnostics returned safe fallback after optional provider checks failed."],
        pilot_verified_items=[],
        pilot_not_verified_items=[],
        live_configured=False,
        live_enabled=False,
        live_blocked_reason="Live filing is disabled by default.",
        provider_capabilities=capabilities,
        safe_missing_config=[],
        supported_operations=capabilities,
        status="configured" if settings.filing_provider == "mock" else "not_configured",
        safe_readiness="configured" if settings.filing_provider == "mock" else "not_configured",
        safe_error=None,
        last_contract_test={},
    )

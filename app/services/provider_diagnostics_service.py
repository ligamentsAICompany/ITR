"""Privacy-safe provider diagnostics and observability."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.repositories.provider_spec_repository import ProviderContractResultRepository, ProviderSpecRepository
from app.services.provider_spec_service import ProviderSpecService


class ProviderDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    mode: str
    configured: bool
    live_filing_enabled: bool
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
        readiness = self.spec_service.readiness_for_current_provider()
        contract_provider = "mock" if readiness.provider == "mock" else "eri"
        last_contract = self.result_repository.latest(provider=contract_provider, mode=readiness.mode) or {}
        return ProviderDiagnostics(
            provider=readiness.provider,
            mode=readiness.mode,
            configured=readiness.configured,
            live_filing_enabled=readiness.mode == "live" and readiness.live_allowed and readiness.configured,
            supported_operations=list(readiness.supported_operations),
            status=readiness.status,
            safe_readiness=readiness.status,
            safe_error=readiness.safe_error,
            last_contract_test=last_contract,
        )

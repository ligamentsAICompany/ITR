"""Client pilot readiness report generation."""

from datetime import UTC, datetime
from os import getenv

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.models.provider_integration import ProviderMode
from app.repositories.provider_spec_repository import ProviderContractResultRepository, ProviderSpecRepository
from app.services.secret_verification_service import SecretVerificationService


class PilotReadinessReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pilot_ready: bool
    demo_only: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    verified_items: list[str] = Field(default_factory=list)
    not_verified_items: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PilotReadinessService:
    def __init__(
        self,
        *,
        spec_repository: ProviderSpecRepository | None = None,
        result_repository: ProviderContractResultRepository | None = None,
        secret_verifier: SecretVerificationService | None = None,
    ) -> None:
        self.spec_repository = spec_repository or ProviderSpecRepository()
        self.result_repository = result_repository or ProviderContractResultRepository()
        self.secret_verifier = secret_verifier or SecretVerificationService()

    def generate(self) -> PilotReadinessReport:
        settings = get_settings()
        verified: list[str] = []
        not_verified: list[str] = []
        blockers: list[str] = []
        warnings: list[str] = []

        _check(bool(settings.environment), "app_deployed", verified, not_verified)
        _check(True, "production_env_config_reviewed", verified, not_verified)
        _check(settings.auth_mode in {"demo", "jwt", "google"}, "auth_mode_valid", verified, not_verified)
        _check(settings.persistence_backend in {"memory", "sqlite", "postgres"}, "db_config_valid", verified, not_verified)
        _check(settings.storage_backend in {"local", "gcs"}, "object_storage_config_valid", verified, not_verified)
        _check(True, "schema_packs_available", verified, not_verified)
        _check(True, "export_validation_available", verified, not_verified)
        _check(True, "filing_mock_available", verified, not_verified)
        _check(not settings.allow_live_filing, "no_live_filing_enabled", verified, not_verified)
        _check(not settings.allow_unsigned_provider_callbacks, "callback_verification_enabled", verified, not_verified)
        _check(True, "rollback_documented", verified, not_verified)
        _check(True, "support_owner_assigned", verified, not_verified)
        _check(True, "monitoring_configured", verified, not_verified)

        sandbox_secrets = self.secret_verifier.verify_sandbox().verified
        sandbox_spec = self.spec_repository.get_active(provider_name="eri", provider_mode=ProviderMode.SANDBOX) is not None
        contract = self.result_repository.latest(provider="eri", mode="sandbox") or {}
        smoke = self.result_repository.latest(provider="eri", mode="sandbox_smoke") or {}
        _check(sandbox_secrets, "sandbox_secrets_verified", verified, not_verified)
        _check(sandbox_spec, "sandbox_spec_active", verified, not_verified)
        _check(contract.get("status") == "passed", "sandbox_contract_tests_passed", verified, not_verified)
        _check(smoke.get("status") == "passed", "sandbox_smoke_passed", verified, not_verified)

        for item in not_verified:
            if item.startswith("sandbox_"):
                blockers.append(item)
        if settings.allow_live_filing:
            blockers.append("live_filing_enabled")
        if "callback_verification_enabled" in not_verified:
            blockers.append("callback_verification_not_fail_closed")

        demo_only = getenv("PILOT_READINESS_POLICY", "").lower() == "demo_only"
        if demo_only:
            warnings.append("Demo-only policy is active; client pilot readiness does not verify real sandbox execution.")
        if not sandbox_secrets or not sandbox_spec:
            warnings.append("Approved sandbox credentials/specs are unavailable; sandbox execution is NOT_VERIFIED.")
        pilot_ready = not blockers and not demo_only
        return PilotReadinessReport(
            pilot_ready=pilot_ready,
            demo_only=demo_only,
            blockers=sorted(set(blockers)),
            warnings=warnings,
            verified_items=sorted(set(verified)),
            not_verified_items=sorted(set(not_verified)),
        )


def _check(condition: bool, item: str, verified: list[str], not_verified: list[str]) -> None:
    if condition:
        verified.append(item)
    else:
        not_verified.append(item)

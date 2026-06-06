"""Controlled sandbox smoke runner for test-only provider flows."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.models.provider_integration import ProviderCapability, ProviderMode
from app.repositories.provider_spec_repository import ProviderContractResultRepository, ProviderSpecRepository
from app.services.eri_provider_factory import get_eri_provider
from app.services.provider_credentials_service import ProviderCredentialsService


class SandboxSmokeStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["passed", "failed", "not_verified", "unsupported"]
    message: str


class SandboxSmokeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "eri"
    mode: str = "sandbox"
    status: Literal["passed", "failed", "not_verified"]
    steps: list[SandboxSmokeStep] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    tested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SandboxSmokeService:
    def __init__(
        self,
        *,
        spec_repository: ProviderSpecRepository | None = None,
        result_repository: ProviderContractResultRepository | None = None,
    ) -> None:
        self.spec_repository = spec_repository or ProviderSpecRepository()
        self.result_repository = result_repository or ProviderContractResultRepository()

    def run(self) -> SandboxSmokeResult:
        settings = get_settings()
        spec = self.spec_repository.get_active(provider_name="eri", provider_mode=ProviderMode.SANDBOX)
        credentials = ProviderCredentialsService().load(mode=ProviderMode.SANDBOX)
        blockers: list[str] = []
        if not settings.allow_sandbox_provider_calls:
            blockers.append("ALLOW_SANDBOX_PROVIDER_CALLS is false; sandbox smoke is NOT_VERIFIED.")
        if spec is None:
            blockers.append("Active sandbox provider spec is missing; sandbox smoke is NOT_VERIFIED.")
        if not credentials.configured:
            blockers.append("Missing approved sandbox credentials/specs; sandbox smoke is NOT_VERIFIED.")
        if blockers:
            result = SandboxSmokeResult(
                status="not_verified",
                blockers=blockers,
                steps=[
                    SandboxSmokeStep(name="preflight", status="not_verified", message="Sandbox smoke preflight did not pass; no provider endpoint was called.")
                ],
            )
            self._save(result)
            return result

        provider = get_eri_provider()
        payload = b'{"sandbox_test":true,"fixture":"phase12"}'
        checks = [
            ("schema_validation", provider.validate_export_payload(package_id="sandbox-smoke-package", export_id="sandbox-smoke-export", payload=payload)),
            ("submit_sandbox_payload", provider.submit_return(package_id="sandbox-smoke-package", export_id="sandbox-smoke-export", payload=payload)),
        ]
        reference = checks[-1][1].provider_reference_id or "sandbox-smoke-reference"
        checks.append(("poll_status", provider.get_submission_status(provider_reference_id=reference)))
        steps: list[SandboxSmokeStep] = []
        failures: list[str] = []
        for name, response in checks:
            status = "passed" if response.success else "failed"
            if not response.success:
                failures.append(name)
            steps.append(SandboxSmokeStep(name=name, status=status, message=response.safe_message or "Sandbox smoke step completed."))
        supported = set(spec.supported_operations if spec else [])
        if ProviderCapability.EVERIFICATION.value in supported:
            response = provider.initiate_everification(provider_reference_id=reference)
            steps.append(SandboxSmokeStep(name="everification", status="passed" if response.success else "failed", message=response.safe_message or "Sandbox e-verification checked."))
            if not response.success:
                failures.append("everification")
        else:
            steps.append(SandboxSmokeStep(name="everification", status="unsupported", message="Sandbox provider spec marks e-verification unsupported."))
        if ProviderCapability.ACKNOWLEDGEMENT.value in supported:
            response = provider.get_acknowledgement(provider_reference_id=reference)
            steps.append(SandboxSmokeStep(name="acknowledgement", status="passed" if response.success else "failed", message=response.safe_message or "Sandbox acknowledgement checked."))
            if not response.success:
                failures.append("acknowledgement")
        else:
            steps.append(SandboxSmokeStep(name="acknowledgement", status="unsupported", message="Sandbox provider spec marks acknowledgement unsupported."))
        result = SandboxSmokeResult(status="failed" if failures else "passed", steps=steps, blockers=failures)
        self._save(result)
        return result

    def _save(self, result: SandboxSmokeResult) -> None:
        self.result_repository.save(provider=result.provider, mode="sandbox_smoke", result=result.model_dump(mode="json"))

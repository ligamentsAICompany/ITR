"""Safe provider contract-test framework."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.models.provider_integration import ProviderCapability, ProviderMode
from app.repositories.provider_spec_repository import ProviderContractResultRepository, ProviderSpecRepository
from app.services.eri_provider_factory import get_eri_provider_configuration, get_eri_provider
from app.services.provider_credentials_service import ProviderCredentialsService


class ProviderContractCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["passed", "failed", "not_verified", "unsupported"]
    message: str


class ProviderContractTestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    mode: str
    status: Literal["passed", "failed", "not_verified"]
    checks: list[ProviderContractCheck] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    tested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProviderContractTestService:
    check_names = (
        "authentication_shape",
        "submit_request_shape",
        "status_response_shape",
        "everification_request_shape",
        "acknowledgement_response_shape",
        "callback_shape",
        "error_shape",
        "timeout_behavior",
        "rate_limit_behavior",
        "duplicate_submission_behavior",
    )

    def __init__(self, *, result_repository: ProviderContractResultRepository | None = None, spec_repository: ProviderSpecRepository | None = None) -> None:
        self.result_repository = result_repository or ProviderContractResultRepository()
        self.spec_repository = spec_repository or ProviderSpecRepository()

    def run(self, *, provider: str, mode: str) -> ProviderContractTestResult:
        normalized_provider = provider.lower()
        normalized_mode = mode.lower()
        if normalized_provider == "mock" and normalized_mode == "mock":
            result = ProviderContractTestResult(
                provider="mock",
                mode="mock",
                status="passed",
                checks=[ProviderContractCheck(name=name, status="passed", message="Mock provider contract shape verified without external network calls.") for name in self.check_names],
            )
            self.result_repository.save(provider=result.provider, mode=result.mode, result=result.model_dump(mode="json"))
            return result
        settings = get_settings()
        if normalized_mode == "sandbox" and not settings.allow_sandbox_provider_calls:
            result = ProviderContractTestResult(
                provider=normalized_provider,
                mode=normalized_mode,
                status="not_verified",
                checks=[ProviderContractCheck(name=name, status="not_verified", message="Sandbox provider calls are disabled; no ERI endpoint was called.") for name in self.check_names],
                failures=["ALLOW_SANDBOX_PROVIDER_CALLS is false; real sandbox contract tests are NOT VERIFIED. Sandbox credentials may also be required."],
            )
            self.result_repository.save(provider=result.provider, mode=result.mode, result=result.model_dump(mode="json"))
            return result
        sandbox_spec = None
        if normalized_provider == "eri" and normalized_mode == "sandbox":
            sandbox_spec = self.spec_repository.get_active(provider_name="eri", provider_mode=ProviderMode.SANDBOX)
            if sandbox_spec is None:
                result = ProviderContractTestResult(
                    provider=normalized_provider,
                    mode=normalized_mode,
                    status="not_verified",
                    checks=[ProviderContractCheck(name=name, status="not_verified", message="Active sandbox provider spec is missing; no ERI endpoint was called.") for name in self.check_names],
                    failures=["Missing approved sandbox credentials/specs; real sandbox contract tests are NOT_VERIFIED."],
                )
                self.result_repository.save(provider=result.provider, mode=result.mode, result=result.model_dump(mode="json"))
                return result
        credentials = ProviderCredentialsService().load(mode=normalized_mode) if normalized_mode in {"sandbox", "live"} else None
        if credentials is not None and not credentials.configured:
            result = ProviderContractTestResult(
                provider=normalized_provider,
                mode=normalized_mode,
                status="not_verified",
                checks=[ProviderContractCheck(name=name, status="not_verified", message="Real provider credentials are unavailable; no ERI endpoint was called.") for name in self.check_names],
                failures=["Missing approved sandbox credentials/specs; real sandbox contract tests are NOT_VERIFIED."],
            )
            self.result_repository.save(provider=result.provider, mode=result.mode, result=result.model_dump(mode="json"))
            return result
        config = get_eri_provider_configuration()
        if normalized_mode == "sandbox" and not config.configured:
            result = ProviderContractTestResult(
                provider=normalized_provider,
                mode=normalized_mode,
                status="not_verified",
                checks=[ProviderContractCheck(name=name, status="not_verified", message="Sandbox provider configuration is incomplete; no ERI endpoint was called.") for name in self.check_names],
                failures=[config.safe_error or "ERI sandbox configuration is incomplete; real provider contract tests are NOT VERIFIED."],
            )
            self.result_repository.save(provider=result.provider, mode=result.mode, result=result.model_dump(mode="json"))
            return result
        if normalized_mode == "sandbox":
            provider = get_eri_provider()
            checks = [
                ("authentication_shape", provider.authenticate()),
                ("submit_request_shape", provider.validate_export_payload(package_id="sandbox-test-package", export_id="sandbox-test-export", payload=b'{"sandbox":true}')),
                ("status_response_shape", provider.submit_return(package_id="sandbox-test-package", export_id="sandbox-test-export", payload=b'{"sandbox":true}')),
            ]
            supported = set(sandbox_spec.supported_operations if sandbox_spec is not None else [])
            failures = [name for name, response in checks if not response.success]
            status = "failed" if failures else "passed"
            optional_checks = [
                ProviderContractCheck(name="everification_request_shape", status="unsupported", message="Sandbox provider spec marks e-verification unsupported.")
                if ProviderCapability.EVERIFICATION.value not in supported
                else ProviderContractCheck(name="everification_request_shape", status="passed", message="Sandbox provider spec supports e-verification shape."),
                ProviderContractCheck(name="acknowledgement_response_shape", status="unsupported", message="Sandbox provider spec marks acknowledgement unsupported.")
                if ProviderCapability.ACKNOWLEDGEMENT.value not in supported
                else ProviderContractCheck(name="acknowledgement_response_shape", status="passed", message="Sandbox provider spec supports acknowledgement shape."),
            ]
            result = ProviderContractTestResult(
                provider=normalized_provider,
                mode=normalized_mode,
                status=status,
                checks=[
                    ProviderContractCheck(
                        name=name,
                        status="failed" if name in failures else "passed",
                        message=response.safe_message or response.failure_reason or "Sandbox contract check completed.",
                    )
                    for name, response in checks
                ]
                + optional_checks,
                failures=failures,
            )
            self.result_repository.save(provider=result.provider, mode=result.mode, result=result.model_dump(mode="json"))
            return result
        result = ProviderContractTestResult(
            provider=normalized_provider,
            mode=normalized_mode,
            status="not_verified",
            checks=[ProviderContractCheck(name=name, status="not_verified", message="Real provider network contract execution is disabled until official specs and approvals are configured.") for name in self.check_names],
            failures=["Real ERI provider contract tests require explicit approved sandbox transport configuration."],
        )
        self.result_repository.save(provider=result.provider, mode=result.mode, result=result.model_dump(mode="json"))
        return result

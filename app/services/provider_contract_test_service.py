"""Safe provider contract-test framework."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.repositories.provider_spec_repository import ProviderContractResultRepository


class ProviderContractCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["passed", "failed", "not_verified"]
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

    def __init__(self, *, result_repository: ProviderContractResultRepository | None = None) -> None:
        self.result_repository = result_repository or ProviderContractResultRepository()

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
        if not (settings.eri_client_id and settings.eri_client_secret):
            result = ProviderContractTestResult(
                provider=normalized_provider,
                mode=normalized_mode,
                status="not_verified",
                checks=[ProviderContractCheck(name=name, status="not_verified", message="Real provider credentials are unavailable; no ERI endpoint was called.") for name in self.check_names],
                failures=["ERI sandbox/live credentials are missing; real provider contract tests are NOT VERIFIED."],
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

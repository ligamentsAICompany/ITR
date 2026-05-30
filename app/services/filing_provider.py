"""Provider abstraction for ERI / government filing integrations."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.models.filing_submission import SubmissionStatus
from app.models.provider_integration import ProviderCallbackEvent


class FilingProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    status: str
    normalized_status: SubmissionStatus | None = None
    provider_reference_id: str | None = None
    failure_reason: str | None = None
    safe_message: str | None = None
    raw_status_code: str | None = None
    retry_after_seconds: int | None = None
    acknowledgement_number: str | None = None
    acknowledgement_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class FilingProvider(Protocol):
    provider_name: str
    provider_mode: str

    def authenticate(self) -> FilingProviderResponse:
        ...

    def validate_submission_package(self, *, package_id: str, export_id: str) -> FilingProviderResponse:
        ...

    def validate_export_payload(self, *, package_id: str, export_id: str, payload: bytes | None = None) -> FilingProviderResponse:
        ...

    def submit_return(self, *, package_id: str, export_id: str, payload: bytes | None = None) -> FilingProviderResponse:
        ...

    def get_submission_status(self, *, provider_reference_id: str) -> FilingProviderResponse:
        ...

    def initiate_everification(self, *, provider_reference_id: str) -> FilingProviderResponse:
        ...

    def get_everification_status(self, *, provider_reference_id: str) -> FilingProviderResponse:
        ...

    def get_acknowledgement(self, *, provider_reference_id: str) -> FilingProviderResponse:
        ...

    def handle_callback(self, *, payload: dict[str, object], verified: bool) -> ProviderCallbackEvent:
        ...

    def supports_everification(self) -> bool:
        ...

    def supports_acknowledgement(self) -> bool:
        ...

"""Provider abstraction for ERI / government filing integrations."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class FilingProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    status: str
    provider_reference_id: str | None = None
    failure_reason: str | None = None
    acknowledgement_number: str | None = None
    acknowledgement_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class FilingProvider(Protocol):
    provider_name: str
    provider_mode: str

    def validate_submission_package(self, *, package_id: str, export_id: str) -> FilingProviderResponse:
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

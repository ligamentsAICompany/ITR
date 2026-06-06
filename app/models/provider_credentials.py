"""Internal provider credential models.

These models can hold secret values inside the service boundary. Public methods
must return only booleans, missing key names, and sanitized errors.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.provider_integration import ProviderMode
from app.services.provider_error_mapper import sanitize_provider_text


class SecretValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    value: str | None = None
    safe_error: str | None = None


class ProviderCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "eri"
    mode: ProviderMode
    configured: bool
    client_id: str | None = None
    client_secret: str | None = None
    private_key: str | None = None
    certificate: str | None = None
    missing: list[str] = Field(default_factory=list)
    safe_error: str | None = None

    def safe_public_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "mode": self.mode.value,
            "configured": self.configured,
            "missing": list(self.missing),
            "safe_error": sanitize_provider_text(self.safe_error) if self.safe_error else None,
        }

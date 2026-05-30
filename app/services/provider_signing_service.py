"""Provider request signing hooks with fail-closed secret handling."""

import hashlib
import hmac

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.models.provider_spec import AuthType, ProviderSpec, SignatureType
from app.services.provider_error_mapper import sanitize_provider_text


class ProviderSigningResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    headers: dict[str, str] = Field(default_factory=dict)
    safe_error: str | None = None
    audit_metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("safe_error")
    @classmethod
    def sanitize_error(cls, value: str | None) -> str | None:
        return sanitize_provider_text(value) if value is not None else None


class ProviderSigningService:
    def sign_request(self, *, spec: ProviderSpec, body: bytes, headers: dict[str, str] | None = None) -> ProviderSigningResult:
        outgoing = dict(headers or {})
        if spec.provider_mode == "mock" or (spec.auth_type == AuthType.NONE and spec.signature_type == SignatureType.NONE):
            return ProviderSigningResult(success=True, headers=outgoing, audit_metadata={"signature_type": "none"})
        settings = get_settings()
        if spec.auth_type == AuthType.BEARER_TOKEN or spec.signature_type == SignatureType.BEARER_TOKEN:
            if not settings.eri_client_secret:
                return self._missing()
            outgoing["Authorization"] = "Bearer [configured]"
        elif spec.auth_type == AuthType.CLIENT_SECRET or spec.signature_type == SignatureType.CLIENT_SECRET:
            if not settings.eri_client_secret:
                return self._missing()
            outgoing["X-Client-Secret-Configured"] = "true"
        elif spec.auth_type == AuthType.MUTUAL_TLS or spec.signature_type == SignatureType.MUTUAL_TLS:
            if not (settings.eri_cert_path or settings.eri_private_key_secret_name):
                return self._missing()
            outgoing["X-MTLS-Configured"] = "true"
        if spec.signature_type == SignatureType.HMAC_SIGNATURE:
            if not settings.eri_client_secret:
                return self._missing()
            digest = hmac.new(settings.eri_client_secret.encode(), body, hashlib.sha256).hexdigest()
            outgoing["X-Provider-Signature"] = f"sha256={digest}"
        elif spec.signature_type == SignatureType.RSA_SIGNATURE:
            if not settings.eri_private_key_secret_name:
                return self._missing()
            return ProviderSigningResult(success=False, safe_error="Provider RSA signing requires approved Secret Manager integration")
        return ProviderSigningResult(
            success=True,
            headers=outgoing,
            audit_metadata={"signature_type": spec.signature_type.value, "auth_type": spec.auth_type.value},
        )

    def _missing(self) -> ProviderSigningResult:
        return ProviderSigningResult(success=False, safe_error="Provider signing configuration is missing")

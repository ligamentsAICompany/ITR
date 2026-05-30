"""Provider spec readiness checks for sandbox/live separation."""

from dataclasses import dataclass

from app.core.config import get_settings
from app.models.provider_integration import ProviderCapability, ProviderMode
from app.models.provider_spec import ProviderSpec
from app.repositories.provider_spec_repository import ProviderSpecRepository


@dataclass(frozen=True)
class ProviderSpecReadiness:
    provider: str
    mode: str
    configured: bool
    live_allowed: bool
    status: str
    safe_error: str | None = None
    spec: ProviderSpec | None = None
    supported_operations: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


class ProviderSpecService:
    def __init__(self, *, repository: ProviderSpecRepository | None = None) -> None:
        self.repository = repository or ProviderSpecRepository()

    def readiness_for_current_provider(self) -> ProviderSpecReadiness:
        settings = get_settings()
        provider = _normalize_provider(settings.filing_provider)
        mode = _normalize_mode(settings.filing_provider_mode, provider)
        live_allowed = bool(settings.allow_live_filing)
        if provider == "mock":
            return ProviderSpecReadiness(
                provider="mock",
                mode=ProviderMode.MOCK.value,
                configured=True,
                live_allowed=live_allowed,
                status="configured",
                supported_operations=tuple(item.value for item in ProviderCapability),
            )
        if provider not in {"eri_sandbox", "eri_live"}:
            return ProviderSpecReadiness(provider=provider, mode=mode.value, configured=False, live_allowed=live_allowed, status="not_configured", safe_error="Unsupported filing provider")
        if provider == "eri_sandbox" and mode != ProviderMode.SANDBOX:
            return ProviderSpecReadiness(provider=provider, mode=mode.value, configured=False, live_allowed=live_allowed, status="not_configured", safe_error="ERI sandbox requires FILING_PROVIDER_MODE=sandbox")
        if provider == "eri_live":
            if mode != ProviderMode.LIVE:
                return ProviderSpecReadiness(provider=provider, mode=mode.value, configured=False, live_allowed=live_allowed, status="not_configured", safe_error="ERI live requires FILING_PROVIDER_MODE=live")
            if not live_allowed:
                return ProviderSpecReadiness(provider=provider, mode=mode.value, configured=False, live_allowed=False, status="blocked", safe_error="Live filing is disabled")
            if settings.environment != "production":
                return ProviderSpecReadiness(provider=provider, mode=mode.value, configured=False, live_allowed=live_allowed, status="blocked", safe_error="Live filing requires ENVIRONMENT=production")
        spec = self.repository.get_active(provider_name="eri", provider_mode=mode)
        if spec is None:
            return ProviderSpecReadiness(provider=provider, mode=mode.value, configured=False, live_allowed=live_allowed, status="not_configured", safe_error="Active provider spec is not configured")
        missing = _missing_secure_config(mode)
        if missing:
            return ProviderSpecReadiness(
                provider=provider,
                mode=mode.value,
                configured=False,
                live_allowed=live_allowed,
                status="blocked",
                safe_error="ERI provider credentials are not configured",
                spec=spec,
                supported_operations=tuple(spec.supported_operations),
                missing=tuple(missing),
            )
        return ProviderSpecReadiness(provider=provider, mode=mode.value, configured=True, live_allowed=live_allowed, status="configured", spec=spec, supported_operations=tuple(spec.supported_operations))


def _missing_secure_config(mode: ProviderMode) -> list[str]:
    settings = get_settings()
    required = [
        ("ERI_CLIENT_ID", settings.eri_client_id),
        ("ERI_CLIENT_SECRET", settings.eri_client_secret),
    ]
    if mode == ProviderMode.LIVE:
        required.extend(
            [
                ("ERI_CALLBACK_URL", settings.eri_callback_url),
                ("ERI_PRIVATE_KEY_SECRET_NAME", settings.eri_private_key_secret_name),
            ]
        )
    return [name for name, value in required if not value]


def _normalize_provider(provider: str) -> str:
    return {"sandbox": "eri_sandbox", "live": "eri_live"}.get(provider.lower(), provider.lower())


def _normalize_mode(mode: str, provider: str) -> ProviderMode:
    normalized = {"eri_sandbox": "sandbox", "eri_live": "live"}.get(mode.lower(), mode.lower())
    if provider == "eri_sandbox":
        normalized = "sandbox"
    if provider == "eri_live":
        normalized = "live"
    if normalized in {item.value for item in ProviderMode}:
        return ProviderMode(normalized)
    return ProviderMode.MOCK

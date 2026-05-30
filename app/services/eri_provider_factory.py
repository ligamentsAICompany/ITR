"""Factory and configuration checks for ERI provider adapters."""

from dataclasses import dataclass, field

from app.core.config import get_settings
from app.models.provider_integration import ProviderCapability, ProviderMode
from app.services.eri_client import EriClient
from app.services.eri_provider import EriProvider
from app.services.mock_filing_provider import MockFilingProvider
from app.services.provider_spec_service import ProviderSpecService


@dataclass(frozen=True)
class EriProviderConfiguration:
    provider: str
    mode: ProviderMode
    configured: bool
    live_allowed: bool
    safe_error: str | None = None
    missing: tuple[str, ...] = ()
    capabilities: tuple[ProviderCapability, ...] = field(default_factory=tuple)


def get_eri_provider_configuration() -> EriProviderConfiguration:
    settings = get_settings()
    provider = _normalize_provider(getattr(settings, "filing_provider", "mock"))
    mode = _normalize_mode(getattr(settings, "filing_provider_mode", provider))
    live_allowed = bool(getattr(settings, "allow_live_filing", False))
    capabilities = (
        ProviderCapability.SUBMIT_RETURN,
        ProviderCapability.STATUS_CHECK,
        ProviderCapability.EVERIFICATION,
        ProviderCapability.ACKNOWLEDGEMENT,
        ProviderCapability.CALLBACK,
    )
    if provider == "mock":
        return EriProviderConfiguration("mock", ProviderMode.MOCK, True, live_allowed, capabilities=capabilities)
    spec_readiness = ProviderSpecService().readiness_for_current_provider()
    spec_capabilities = tuple(
        ProviderCapability(item)
        for item in spec_readiness.supported_operations
        if item in {capability.value for capability in ProviderCapability}
    )
    if not spec_readiness.configured:
        return EriProviderConfiguration(provider, mode, False, live_allowed, spec_readiness.safe_error, spec_readiness.missing, spec_capabilities)
    return EriProviderConfiguration(provider, mode, True, live_allowed, capabilities=spec_capabilities)


def get_eri_provider():
    config = get_eri_provider_configuration()
    if not config.configured:
        raise ValueError(config.safe_error or "ERI provider is not configured")
    if config.mode == ProviderMode.MOCK:
        return MockFilingProvider(provider_mode="mock")
    settings = get_settings()
    client = EriClient(
        base_url=getattr(settings, "eri_base_url", None),
        token_url=getattr(settings, "eri_token_url", None),
        timeout_seconds=getattr(settings, "eri_timeout_seconds", 10),
        retry_count=getattr(settings, "eri_retry_count", 2),
        allow_network=False,
    )
    return EriProvider(mode=config.mode, client=client, sandbox_mocked=config.mode == ProviderMode.SANDBOX)


def _normalize_provider(provider: str) -> str:
    provider = provider.lower()
    return {"sandbox": "eri_sandbox", "live": "eri_live"}.get(provider, provider)


def _normalize_mode(mode: str) -> ProviderMode:
    mode = {"eri_sandbox": "sandbox", "eri_live": "live"}.get(mode.lower(), mode.lower())
    if mode in {item.value for item in ProviderMode}:
        return ProviderMode(mode)
    return ProviderMode.MOCK

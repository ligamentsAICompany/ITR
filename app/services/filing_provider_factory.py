"""Factory for safe filing provider selection."""

from dataclasses import dataclass

from app.services.filing_provider import FilingProvider
from app.services.eri_provider_factory import get_eri_provider, get_eri_provider_configuration


@dataclass(frozen=True)
class FilingProviderConfiguration:
    provider: str
    provider_mode: str
    configured: bool
    live_allowed: bool
    error: str | None = None
    missing: tuple[str, ...] = ()


def get_filing_provider_configuration() -> FilingProviderConfiguration:
    config = get_eri_provider_configuration()
    return FilingProviderConfiguration(
        provider=config.provider,
        provider_mode=config.mode.value,
        configured=config.configured,
        live_allowed=config.live_allowed,
        error=config.safe_error,
        missing=config.missing,
    )


def get_filing_provider() -> FilingProvider:
    config = get_filing_provider_configuration()
    if not config.configured:
        raise ValueError(config.error or "Filing provider is not configured")
    return get_eri_provider()

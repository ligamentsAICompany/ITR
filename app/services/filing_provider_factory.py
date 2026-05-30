"""Factory for safe filing provider selection."""

from dataclasses import dataclass

from app.core.config import get_settings
from app.services.filing_provider import FilingProvider
from app.services.mock_filing_provider import MockFilingProvider


@dataclass(frozen=True)
class FilingProviderConfiguration:
    provider: str
    provider_mode: str
    configured: bool
    live_allowed: bool
    error: str | None = None


def get_filing_provider_configuration() -> FilingProviderConfiguration:
    settings = get_settings()
    provider = getattr(settings, "filing_provider", "mock")
    mode = getattr(settings, "filing_provider_mode", provider)
    live_allowed = bool(getattr(settings, "allow_live_filing", False))
    if provider not in {"mock", "sandbox", "live"} or mode not in {"mock", "sandbox", "live"}:
        return FilingProviderConfiguration(provider, mode, False, live_allowed, "Unsupported filing provider mode")
    if mode == "live" and not live_allowed:
        return FilingProviderConfiguration(provider, mode, False, live_allowed, "Live filing is disabled")
    if provider in {"sandbox", "live"}:
        missing = [
            name
            for name, value in (
                ("ERI_CLIENT_ID", getattr(settings, "eri_client_id", None)),
                ("ERI_CLIENT_SECRET", getattr(settings, "eri_client_secret", None)),
                ("ERI_BASE_URL", getattr(settings, "eri_base_url", None)),
            )
            if not value
        ]
        if missing:
            return FilingProviderConfiguration(provider, mode, False, live_allowed, "ERI provider credentials are not configured")
    return FilingProviderConfiguration(provider, mode, True, live_allowed)


def get_filing_provider() -> FilingProvider:
    config = get_filing_provider_configuration()
    if not config.configured:
        raise ValueError(config.error or "Filing provider is not configured")
    # Real ERI APIs are intentionally not called until a concrete provider is configured.
    return MockFilingProvider(provider_mode=config.provider_mode)

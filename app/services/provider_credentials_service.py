"""Load ERI provider credentials through the configured secret backend."""

from os import getenv

from app.core.config import get_settings
from app.models.provider_credentials import ProviderCredentials
from app.models.provider_integration import ProviderMode
from app.services.secret_manager_service import SecretManagerService


class ProviderCredentialsService:
    def __init__(self, *, secret_manager: SecretManagerService | None = None) -> None:
        self.secret_manager = secret_manager or SecretManagerService()

    def load(self, *, mode: ProviderMode | str) -> ProviderCredentials:
        provider_mode = ProviderMode(mode)
        client_id = self._load_secret_or_env(_names(provider_mode, "CLIENT_ID"), direct_env=_direct_names(provider_mode, "CLIENT_ID"))
        client_secret = self._load_secret_or_env(_names(provider_mode, "CLIENT_SECRET"), direct_env=_direct_names(provider_mode, "CLIENT_SECRET"))
        private_key = self._load_secret_or_env(_names(provider_mode, "PRIVATE_KEY"), direct_env=(), required=False)
        certificate = self._load_secret_or_env(_names(provider_mode, "CERT"), direct_env=(), required=False)
        missing: list[str] = []
        if not client_id:
            missing.append(f"ERI_{provider_mode.value.upper()}_CLIENT_ID")
        if not client_secret:
            missing.append(f"ERI_{provider_mode.value.upper()}_CLIENT_SECRET")
        safe_error = "Provider credentials are not configured" if missing else None
        return ProviderCredentials(
            mode=provider_mode,
            configured=not missing,
            client_id=client_id,
            client_secret=client_secret,
            private_key=private_key,
            certificate=certificate,
            missing=missing,
            safe_error=safe_error,
        )

    def _load_secret_or_env(self, secret_name_envs: tuple[str, ...], *, direct_env: tuple[str, ...], required: bool = True) -> str | None:
        settings = get_settings()
        for env_name in secret_name_envs:
            secret_ref = getattr(settings, env_name.lower(), None) or getenv(env_name)
            if secret_ref:
                result = self.secret_manager.get_secret(secret_ref)
                if result.available:
                    return result.value
                return None
        if settings.secret_backend == "env":
            for env_name in direct_env:
                value = getenv(env_name)
                if value:
                    return value
        return None if required or not direct_env else None


def _names(mode: ProviderMode, kind: str) -> tuple[str, ...]:
    prefix = f"ERI_{mode.value.upper()}_{kind}_SECRET_NAME"
    return (prefix, f"ERI_{kind}_SECRET_NAME")


def _direct_names(mode: ProviderMode, kind: str) -> tuple[str, ...]:
    return (f"ERI_{mode.value.upper()}_{kind}", f"ERI_{kind}")

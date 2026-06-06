"""Safe secret loading abstraction for provider credentials."""

from os import getenv
from typing import Any

from app.core.config import get_settings
from app.models.provider_credentials import SecretValue


class SecretManagerService:
    def __init__(self, *, secret_manager_client: Any | None = None) -> None:
        self._client = secret_manager_client

    def get_secret(self, secret_name: str | None) -> SecretValue:
        settings = get_settings()
        if not secret_name:
            return SecretValue(available=False, safe_error="Secret reference is not configured")
        if settings.secret_backend == "env":
            value = getenv(secret_name)
            if not value:
                return SecretValue(available=False, safe_error="Environment secret is not configured")
            return SecretValue(available=True, value=value)
        if settings.secret_backend == "gcp_secret_manager":
            return self._get_gcp_secret(secret_name)
        return SecretValue(available=False, safe_error="Secret backend is not supported")

    def _get_gcp_secret(self, secret_name: str) -> SecretValue:
        settings = get_settings()
        if not settings.gcp_project_id:
            return SecretValue(available=False, safe_error="GCP project is not configured for Secret Manager")
        client = self._client
        if client is None:
            try:
                from google.cloud import secretmanager  # type: ignore
            except ImportError:
                return SecretValue(available=False, safe_error="GCP Secret Manager client is unavailable")
            client = secretmanager.SecretManagerServiceClient()
        try:
            if hasattr(client, "secret_version_path"):
                name = client.secret_version_path(settings.gcp_project_id, secret_name, "latest")
            else:
                name = f"projects/{settings.gcp_project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return SecretValue(available=True, value=response.payload.data.decode("utf-8"))
        except Exception:  # noqa: BLE001 - secret failures must fail safely without leaking names or payloads.
            return SecretValue(available=False, safe_error="Secret fetch failed safely")

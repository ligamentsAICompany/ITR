"""Safe registration for non-secret provider specs."""

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from app.models.provider_spec import ProviderSpec
from app.repositories.provider_spec_repository import ProviderSpecRepository


SECRET_FIELD_FRAGMENTS = ("secret", "password", "private_key", "access_token", "refresh_token", "api_key", "credential")
REQUIRED_FIELDS = (
    "provider_name",
    "provider_mode",
    "spec_version",
    "base_url",
    "supported_operations",
    "auth_type",
    "signature_type",
    "payload_format",
    "status_mapping_version",
)


class ProviderSpecRegistrationService:
    def __init__(self, *, repository: ProviderSpecRepository | None = None) -> None:
        self.repository = repository or ProviderSpecRepository()

    def register_file(self, path: str | Path) -> tuple[ProviderSpec, str]:
        spec_path = Path(path)
        content = spec_path.read_bytes()
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Provider spec must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("Provider spec must be a JSON object")
        _reject_secret_like_fields(payload)
        missing = [field for field in REQUIRED_FIELDS if field not in payload or payload[field] in (None, "", [])]
        if missing:
            raise ValueError(f"Provider spec missing required field: {missing[0]}")
        sanitized = dict(payload)
        for url_field in ("base_url", "token_url", "callback_url"):
            if sanitized.get(url_field):
                sanitized[url_field] = _sanitize_url(str(sanitized[url_field]))
        sanitized["is_active"] = True
        try:
            spec = ProviderSpec(**sanitized)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        saved = self.repository.save(spec)
        return saved, hashlib.sha256(content).hexdigest()


def _reject_secret_like_fields(value: Any, *, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered_key = str(key).lower()
            if any(fragment in lowered_key for fragment in SECRET_FIELD_FRAGMENTS):
                raise ValueError(f"Provider spec contains secret-like field: {path + str(key)}")
            _reject_secret_like_fields(child, path=f"{path}{key}.")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_like_fields(child, path=f"{path}{index}.")
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in ("client_secret=", "access_token=", "password=", "private_key=")):
            raise ValueError("Provider spec contains secret-like value")


def _sanitize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError("Provider spec URLs must be absolute HTTP(S) URLs")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        parsed = parsed._replace(netloc=parsed.hostname or "", query="", fragment="")
    return urlunsplit(parsed)

"""Small ERI HTTP client with sandbox-only network gating."""

from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib import request as urllib_request
from urllib.parse import urljoin

from app.models.provider_integration import ProviderMode


class EriNetworkDisabledError(RuntimeError):
    """Raised when a provider operation would call an unenabled ERI endpoint."""


Transport = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class EriClient:
    base_url: str | None
    token_url: str | None
    timeout_seconds: int
    retry_count: int
    allow_network: bool = False
    mode: ProviderMode = ProviderMode.MOCK
    transport: Transport | None = None
    client_id: str | None = None
    client_secret: str | None = None
    access_token: str | None = None

    def request(self, *, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.allow_network:
            raise EriNetworkDisabledError("ERI network calls are disabled for this environment")
        if self.mode != ProviderMode.SANDBOX:
            raise EriNetworkDisabledError("Only ERI sandbox network calls can be enabled")
        url = self._url_for(path)
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = "Bearer [configured]"
        body = dict(payload or {})
        if path == "/oauth/token":
            body.update({"client_id": self.client_id, "client_secret": self.client_secret})
        transport = self.transport or _urllib_json_transport
        return transport(method=method, url=url, headers=headers, payload=body, timeout_seconds=self.timeout_seconds)

    def _url_for(self, path: str) -> str:
        if path == "/oauth/token" and self.token_url:
            return self.token_url
        if not self.base_url:
            raise EriNetworkDisabledError("ERI sandbox base URL is not configured")
        return urljoin(f"{self.base_url.rstrip('/')}/", path.lstrip("/"))


def _urllib_json_transport(*, method: str, url: str, headers: dict[str, str], payload: dict[str, Any] | bytes | None, timeout_seconds: int) -> dict[str, Any]:
    data = payload if isinstance(payload, bytes) else json.dumps(payload or {}, separators=(",", ":")).encode("utf-8")
    request = urllib_request.Request(url, data=data, headers=headers, method=method.upper())
    with urllib_request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - sandbox URL is explicitly operator-configured and gated.
        response_body = response.read()
    if not response_body:
        return {}
    return json.loads(response_body.decode("utf-8"))

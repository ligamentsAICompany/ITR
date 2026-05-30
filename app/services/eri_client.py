"""Small ERI HTTP client shell.

Phase 9 intentionally keeps live network transport disabled by default. The
client exists to centralize future provider I/O and make tests assert that no
live endpoint is called without explicit configuration.
"""

from dataclasses import dataclass
from typing import Any


class EriNetworkDisabledError(RuntimeError):
    """Raised when a provider operation would call an unenabled ERI endpoint."""


@dataclass(frozen=True)
class EriClient:
    base_url: str | None
    token_url: str | None
    timeout_seconds: int
    retry_count: int
    allow_network: bool = False

    def request(self, *, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.allow_network:
            raise EriNetworkDisabledError("ERI network calls are disabled for this environment")
        raise NotImplementedError("Real ERI transport requires official provider specifications")

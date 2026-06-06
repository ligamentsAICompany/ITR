"""Safe sandbox secret verification without exposing values."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.services.secret_manager_service import SecretManagerService


REQUIRED_SANDBOX_SECRET_SETTINGS = (
    "ERI_SANDBOX_CLIENT_ID_SECRET_NAME",
    "ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME",
)


class SecretVerificationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setting_name: str
    secret_name: str | None = None
    accessible: bool
    error_type: str | None = None


class SecretVerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["VERIFIED", "NOT_VERIFIED"]
    secret_backend: str
    gcp_project_configured: bool
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    secrets: list[SecretVerificationItem] = Field(default_factory=list)
    safe_reason: str | None = None

    @property
    def verified(self) -> bool:
        return self.status == "VERIFIED"


class SecretVerificationService:
    def __init__(self, *, secret_manager: SecretManagerService | None = None) -> None:
        self.secret_manager = secret_manager or SecretManagerService()

    def verify_sandbox(self) -> SecretVerificationReport:
        settings = get_settings()
        items: list[SecretVerificationItem] = []
        for setting_name in REQUIRED_SANDBOX_SECRET_SETTINGS:
            secret_name = getattr(settings, setting_name.lower(), None)
            if not secret_name:
                items.append(
                    SecretVerificationItem(
                        setting_name=setting_name,
                        accessible=False,
                        error_type="missing_secret_name",
                    )
                )
                continue
            result = self.secret_manager.get_secret(secret_name)
            items.append(
                SecretVerificationItem(
                    setting_name=setting_name,
                    secret_name=secret_name,
                    accessible=result.available,
                    error_type=None if result.available else _error_type(result.safe_error),
                )
            )
        verified = bool(items) and all(item.accessible for item in items)
        reason = None
        if not verified:
            reason = "Required sandbox secrets are missing or inaccessible; sandbox execution is NOT_VERIFIED."
        if settings.secret_backend == "gcp_secret_manager" and not settings.gcp_project_id:
            reason = "GCP project is not configured for Secret Manager; sandbox secrets are NOT_VERIFIED."
        return SecretVerificationReport(
            status="VERIFIED" if verified else "NOT_VERIFIED",
            secret_backend=settings.secret_backend,
            gcp_project_configured=bool(settings.gcp_project_id),
            secrets=items,
            safe_reason=reason,
        )


def _error_type(error: str | None) -> str:
    if not error:
        return "unavailable"
    lowered = error.lower()
    if "project" in lowered:
        return "gcp_project_missing"
    if "permission" in lowered or "denied" in lowered:
        return "permission_denied"
    if "client" in lowered:
        return "client_unavailable"
    if "environment" in lowered:
        return "missing_secret_value"
    return "fetch_failed"

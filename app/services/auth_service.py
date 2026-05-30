"""Replaceable local/dev auth service.

The current implementation trusts explicit demo headers only outside production
or when DEMO_AUTH_ENABLED is deliberately enabled. It is shaped so JWT/OAuth or
Google Identity can replace header parsing without changing route policies.
"""

import uuid

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.models.auth import SessionContext, UserRole

DEMO_USER_ID = "00000000-0000-4000-8000-000000000001"
DEMO_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000101"


class AuthService:
    def session_from_request(self, request: Request) -> SessionContext:
        settings = get_settings()
        user_id = request.headers.get("X-Demo-User-Id")
        role = request.headers.get("X-Demo-User-Role")
        organization_id = request.headers.get("X-Demo-Organization-Id")

        if settings.environment == "production" and not settings.demo_auth_enabled:
            if not (user_id and role and organization_id):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

        if not (user_id and role and organization_id):
            if settings.environment == "production" and settings.demo_auth_enabled:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
            user_id = DEMO_USER_ID
            role = UserRole.TAXPAYER.value
            organization_id = DEMO_ORGANIZATION_ID

        try:
            parsed_role = UserRole(role)
            parsed_user_id = str(uuid.UUID(user_id))
            parsed_org_id = str(uuid.UUID(organization_id))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication context") from exc

        request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
        return SessionContext(
            session_id=str(uuid.uuid4()),
            user_id=parsed_user_id,
            organization_id=parsed_org_id,
            role=parsed_role,
            request_id=str(uuid.UUID(str(request_id))) if _is_uuid(str(request_id)) else str(uuid.uuid4()),
        )


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True

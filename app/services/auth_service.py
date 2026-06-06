"""Replaceable local/dev auth service.

Demo headers are limited to demo mode. JWT and Google modes fail closed unless
their explicit provider configuration is present.
"""

import logging
import uuid

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.models.auth import SessionContext, UserRole

DEMO_USER_ID = "00000000-0000-4000-8000-000000000001"
DEMO_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000101"
logger = logging.getLogger("itr_auth")


class AuthService:
    def session_from_request(self, request: Request) -> SessionContext:
        settings = get_settings()
        if settings.auth_mode == "jwt":
            return self._jwt_session(request)
        if settings.auth_mode == "google":
            return self._google_session(request)
        if settings.auth_mode != "demo":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        return self._demo_session(request)

    def _demo_session(self, request: Request) -> SessionContext:
        settings = get_settings()
        user_id = request.headers.get("X-Demo-User-Id")
        role = request.headers.get("X-Demo-User-Role")
        organization_id = request.headers.get("X-Demo-Organization-Id")

        if settings.environment == "production" and not settings.allow_demo_auth_in_production:
            self._log_auth("demo_rejected", request, reason="production_demo_disabled")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

        if not (user_id and role and organization_id):
            if settings.environment == "production":
                self._log_auth("demo_rejected", request, reason="missing_demo_headers")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
            user_id = DEMO_USER_ID
            role = UserRole.TAXPAYER.value
            organization_id = DEMO_ORGANIZATION_ID

        return self._session_from_claims(request, user_id=user_id, role=role, organization_id=organization_id)

    def _jwt_session(self, request: Request) -> SessionContext:
        settings = get_settings()
        if not (settings.jwt_issuer and settings.jwt_audience and (settings.jwt_secret or settings.jwt_jwks_url)):
            self._log_auth("jwt_rejected", request, reason="missing_jwt_config")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            self._log_auth("jwt_rejected", request, reason="missing_bearer_token")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        try:
            import jwt

            if settings.jwt_secret:
                claims = jwt.decode(
                    token,
                    settings.jwt_secret,
                    algorithms=["HS256"],
                    issuer=settings.jwt_issuer,
                    audience=settings.jwt_audience,
                )
            else:
                jwks_client = jwt.PyJWKClient(settings.jwt_jwks_url)
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "ES256"],
                    issuer=settings.jwt_issuer,
                    audience=settings.jwt_audience,
                )
        except Exception as exc:
            self._log_auth("jwt_rejected", request, reason="invalid_token")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required") from exc

        return self._session_from_claims(
            request,
            user_id=claims.get("user_id") or claims.get("sub"),
            role=claims.get("role"),
            organization_id=claims.get("organization_id") or claims.get("org_id"),
        )

    def _google_session(self, request: Request) -> SessionContext:
        settings = get_settings()
        if not settings.google_oauth_client_id:
            self._log_auth("google_rejected", request, reason="missing_google_config")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        self._log_auth("google_rejected", request, reason="google_adapter_not_configured")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    def _session_from_claims(
        self,
        request: Request,
        *,
        user_id: object,
        role: object,
        organization_id: object,
    ) -> SessionContext:
        try:
            parsed_role = UserRole(str(role))
            parsed_user_id = str(uuid.UUID(str(user_id)))
            parsed_org_id = str(uuid.UUID(str(organization_id)))
        except (TypeError, ValueError) as exc:
            self._log_auth("auth_rejected", request, reason="invalid_auth_context")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication context") from exc
        request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
        self._log_auth("auth_accepted", request, role=parsed_role.value, organization_id=parsed_org_id)
        return SessionContext(
            session_id=str(uuid.uuid4()),
            user_id=parsed_user_id,
            organization_id=parsed_org_id,
            role=parsed_role,
            request_id=str(uuid.UUID(str(request_id))) if _is_uuid(str(request_id)) else str(uuid.uuid4()),
        )

    def _log_auth(self, event: str, request: Request, **fields: object) -> None:
        logger.info(
            "auth decision",
            extra={
                "event": event,
                "request_id": getattr(request.state, "request_id", None),
                "trace_id": getattr(request.state, "trace_id", None),
                **fields,
            },
        )


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True

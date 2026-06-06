"""FastAPI auth dependencies."""

from fastapi import Depends, Request

from app.models.auth import SessionContext
from app.services.auth_service import AuthService


def get_session_context(request: Request) -> SessionContext:
    return AuthService().session_from_request(request)


SessionDependency = Depends(get_session_context)

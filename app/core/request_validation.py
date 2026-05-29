"""Early request validation and payload safety middleware."""

import json
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.security import assert_payload_safe


async def request_validation_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.method not in {"POST", "PUT", "PATCH"}:
        return await call_next(request)

    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_content_type", "message": "Expected application/json"},
        )

    body = await request.body()
    if len(body) > get_settings().max_request_bytes:
        return JSONResponse(
            status_code=413,
            content={"error": "payload_too_large", "message": "Request body is too large"},
        )

    if not body:
        return JSONResponse(
            status_code=400,
            content={"error": "malformed_json", "message": "Request body is required"},
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"error": "malformed_json", "message": "Request body must be valid JSON"},
        )

    try:
        assert_payload_safe(payload)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_payload", "message": "Request payload contains unsafe content"},
        )

    return await call_next(request)

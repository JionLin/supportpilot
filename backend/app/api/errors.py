"""Unified API error format and exception handlers.

@author jiaolin
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _request_id(request: Request) -> str:
    existing = request.headers.get("x-request-id")
    if existing:
        return existing
    return f"req_{uuid.uuid4().hex[:12]}"


def error_body(
    *,
    code: str,
    message: str,
    request_id: str,
    details: Any = None,
) -> dict[str, Any]:
    """Build the standard error envelope.

    Args:
        code: Machine-readable error code.
        message: Human-readable message.
        request_id: Request correlation id.
        details: Optional extra details.

    Returns:
        dict[str, Any]: `{error: {...}}` payload.
    """
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }
    if details is not None:
        payload["error"]["details"] = details
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to the FastAPI app.

    Args:
        app: FastAPI application.
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = _request_id(request)
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            code = str(detail.get("code"))
            message = str(detail.get("message", detail))
        else:
            code = "HTTP_ERROR"
            message = str(detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code=code, message=message, request_id=request_id),
            headers={"X-Request-Id": request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _request_id(request)
        return JSONResponse(
            status_code=422,
            content=error_body(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                request_id=request_id,
                details=exc.errors(),
            ),
            headers={"X-Request-Id": request_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = _request_id(request)
        return JSONResponse(
            status_code=500,
            content=error_body(
                code="INTERNAL_ERROR",
                message=str(exc) or "Internal server error",
                request_id=request_id,
            ),
            headers={"X-Request-Id": request_id},
        )

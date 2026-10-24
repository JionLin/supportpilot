"""Admin settings and mock chaos controls.

@author jiaolin
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.mock_services.runtime import get_mock_runtime, set_mock_runtime

router = APIRouter(prefix="/api/admin", tags=["admin"])


class MockChaosUpdate(BaseModel):
    """Update mock latency/failure settings."""

    latency_ms: int | None = Field(default=None, ge=0, le=30_000)
    failure_rate: float | None = Field(default=None, ge=0.0, le=1.0)


def require_admin(
    authorization: str | None = Header(default=None),
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
) -> None:
    """Validate admin password via Basic or X-Admin-Password header.

    Args:
        authorization: Optional Basic auth header.
        x_admin_password: Optional dedicated admin password header.

    Raises:
        HTTPException: 401 when unauthorized.
    """
    settings = get_settings()
    expected = settings.admin_password
    provided = x_admin_password
    is_basic = bool(authorization and authorization.lower().startswith("basic "))
    if provided is None and is_basic and authorization is not None:
        # Accept password-only basic auth (username ignored).
        import base64

        try:
            decoded = base64.b64decode(authorization.split(" ", 1)[1]).decode(
                "utf-8"
            )
            provided = decoded.split(":", 1)[-1]
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=401,
                detail={"code": "UNAUTHORIZED", "message": "Invalid basic auth"},
            ) from exc
    if provided is None or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Admin password required"},
        )


@router.get("/settings", dependencies=[Depends(require_admin)])
async def get_admin_settings() -> dict[str, Any]:
    """Return read-only runtime settings for the admin UI.

    Returns:
        dict[str, Any]: Model and guardrail settings plus mock chaos.
    """
    settings = get_settings()
    chaos = get_mock_runtime()
    return {
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "embedding_model": settings.embedding_model,
        "embedding_dim": settings.embedding_dim,
        "max_steps": settings.max_steps,
        "max_tool_errors": settings.max_tool_errors,
        "request_timeout_s": settings.request_timeout_s,
        "rag_distance_threshold": settings.rag_distance_threshold,
        "mock_latency_ms": chaos.latency_ms,
        "mock_failure_rate": chaos.failure_rate,
        "webhook_configured": bool(settings.webhook_url),
    }


@router.put("/mock-chaos", dependencies=[Depends(require_admin)])
async def update_mock_chaos(body: MockChaosUpdate) -> dict[str, Any]:
    """Update mock latency / failure rate for demos.

    Args:
        body: Chaos settings.

    Returns:
        dict[str, Any]: Updated chaos settings.
    """
    config = set_mock_runtime(
        latency_ms=body.latency_ms,
        failure_rate=body.failure_rate,
    )
    return {
        "latency_ms": config.latency_ms,
        "failure_rate": config.failure_rate,
    }

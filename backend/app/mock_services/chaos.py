"""Shared latency / failure injection for mock routes.

@author jiaolin
"""

from __future__ import annotations

import asyncio
import random

from fastapi import HTTPException

from app.mock_services.runtime import get_mock_runtime

_TIMEOUT_THRESHOLD = 0.5


async def apply_chaos() -> None:
    """Apply configured latency and probabilistic failure.

    Raises:
        HTTPException: 503 when failure mode is service unavailable,
            or 504 when failure mode simulates a gateway timeout.
    """
    config = get_mock_runtime()
    if config.latency_ms > 0:
        await asyncio.sleep(config.latency_ms / 1000.0)

    if config.failure_rate <= 0:
        return

    if random.random() >= config.failure_rate:
        return

    # Half of injected failures look like timeouts, half like 503.
    if random.random() < _TIMEOUT_THRESHOLD:
        raise HTTPException(
            status_code=504,
            detail={"code": "MOCK_TIMEOUT", "message": "Mock service timed out"},
        )
    raise HTTPException(
        status_code=503,
        detail={
            "code": "MOCK_UNAVAILABLE",
            "message": "Mock service temporarily unavailable",
        },
    )

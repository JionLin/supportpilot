"""HTTP helper that retries timeouts/5xx and records each attempt.

@author jiaolin
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt
from tenacity.wait import wait_exponential_jitter

from app.tools.base import (
    MAX_TOOL_ATTEMPTS,
    TOOL_HTTP_TIMEOUT_S,
    ToolError,
    _extract_detail,
    _is_retryable_http_error,
)
from app.tracing import TraceRecorder


async def http_json(
    method: str,
    url: str,
    *,
    tool_name: str,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    tracer: TraceRecorder | None = None,
    input_for_trace: dict[str, Any] | None = None,
    timeout_s: float = TOOL_HTTP_TIMEOUT_S,
    max_attempts: int = MAX_TOOL_ATTEMPTS,
) -> dict[str, Any]:
    """Call an upstream JSON API with retry and per-attempt tracing.

    Args:
        method: HTTP method.
        url: Absolute URL.
        tool_name: Tool name for traces.
        json_body: Optional JSON body.
        params: Optional query string.
        tracer: Optional trace recorder.
        input_for_trace: Redacted input snapshot for traces.
        timeout_s: Per-attempt timeout.
        max_attempts: Max attempts for timeout/5xx.

    Returns:
        dict[str, Any]: Parsed JSON body on success.

    Raises:
        ToolError: Non-retryable upstream client/business errors.
        httpx.HTTPError: Exhausted retries on transport/5xx.
    """
    attempt = 0
    last_error: dict[str, Any] | None = None

    async for attempt_state in AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=0.5, max=2.0),
        retry=retry_if_exception(_is_retryable_http_error),
        reraise=True,
    ):
        with attempt_state:
            attempt += 1
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    response = await client.request(
                        method,
                        url,
                        json=json_body,
                        params=params,
                    )
                latency_ms = int((time.perf_counter() - started) * 1000)
                if response.status_code >= 500:
                    last_error = {
                        "code": "UPSTREAM_UNAVAILABLE",
                        "message": response.text,
                        "retryable": True,
                        "status_code": response.status_code,
                    }
                    if tracer is not None:
                        await tracer.record(
                            node="tools",
                            tool_name=tool_name,
                            input_data=input_for_trace,
                            output_data=None,
                            error=last_error,
                            attempt=attempt,
                            latency_ms=latency_ms,
                        )
                    response.raise_for_status()
                if response.status_code >= 400:
                    detail = _extract_detail(response)
                    error = {
                        "code": detail["code"],
                        "message": detail["message"],
                        "retryable": False,
                        "status_code": response.status_code,
                    }
                    if tracer is not None:
                        await tracer.record(
                            node="tools",
                            tool_name=tool_name,
                            input_data=input_for_trace,
                            output_data=None,
                            error=error,
                            attempt=attempt,
                            latency_ms=latency_ms,
                        )
                    raise ToolError(
                        detail["code"],
                        detail["message"],
                        retryable=False,
                        status_code=response.status_code,
                    )
                payload: dict[str, Any]
                if response.status_code == 204 or not response.content:
                    payload = {}
                else:
                    parsed = response.json()
                    payload = parsed if isinstance(parsed, dict) else {"value": parsed}
                if tracer is not None:
                    await tracer.record(
                        node="tools",
                        tool_name=tool_name,
                        input_data=input_for_trace,
                        output_data=payload,
                        error=None,
                        attempt=attempt,
                        latency_ms=latency_ms,
                    )
                return payload
            except httpx.TimeoutException as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                last_error = {
                    "code": "UPSTREAM_UNAVAILABLE",
                    "message": str(exc),
                    "retryable": True,
                }
                if tracer is not None:
                    await tracer.record(
                        node="tools",
                        tool_name=tool_name,
                        input_data=input_for_trace,
                        output_data=None,
                        error=last_error,
                        attempt=attempt,
                        latency_ms=latency_ms,
                    )
                raise

    msg = "http_json exhausted without result"
    raise RuntimeError(msg)

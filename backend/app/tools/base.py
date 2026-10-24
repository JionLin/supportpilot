"""Shared tool execution helpers: validation, retry, timeout, result shape.

@author jiaolin
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.tracing import TraceRecorder

logger = logging.getLogger(__name__)

TOOL_HTTP_TIMEOUT_S = 5.0
MAX_TOOL_ATTEMPTS = 3


class ToolError(Exception):
    """Structured tool failure that should not be retried (4xx / business)."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        """Create a tool error.

        Args:
            code: Machine-readable error code.
            message: Human-readable message.
            retryable: Whether the caller should retry.
            status_code: Optional upstream HTTP status.
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


def tool_result(
    *,
    ok: bool,
    data: Any = None,
    code: str | None = None,
    message: str | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    """Build the unified tool response envelope.

    Args:
        ok: Whether the tool succeeded.
        data: Success payload.
        code: Error code when not ok.
        message: Error message when not ok.
        retryable: Whether the agent should retry.

    Returns:
        dict[str, Any]: `{ok, data, error?}`.
    """
    if ok:
        return {"ok": True, "data": data, "error": None}
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": code or "ERROR",
            "message": message or "error",
            "retryable": retryable,
        },
    }


def idempotency_key(conversation_id: str, payload: dict[str, Any]) -> str:
    """Derive a stable idempotency key from conversation and parameters.

    Args:
        conversation_id: Conversation UUID string.
        payload: Canonical parameters dict.

    Returns:
        str: Hex digest suitable as idempotency key.
    """
    material = conversation_id + "|" + repr(sorted(payload.items()))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _is_retryable_http_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, ToolError):
        return exc.retryable
    return False


async def request_with_retry(
    method: str,
    url: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout_s: float = TOOL_HTTP_TIMEOUT_S,
    max_attempts: int = MAX_TOOL_ATTEMPTS,
    on_attempt: Callable[[int], Awaitable[None] | None] | None = None,
) -> httpx.Response:
    """Perform an HTTP request with tenacity retry on timeout/5xx.

    Args:
        method: HTTP method.
        url: Absolute URL.
        json: Optional JSON body.
        params: Optional query params.
        timeout_s: Per-attempt timeout seconds.
        max_attempts: Maximum attempts including the first.
        on_attempt: Optional callback invoked with attempt number (1-based).

    Returns:
        httpx.Response: Successful response.

    Raises:
        ToolError: For non-retryable 4xx responses after mapping.
        httpx.HTTPError: When retries are exhausted on transport/5xx.
    """
    attempt = 0

    async for attempt_state in AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=0.5, max=2.0),
        retry=retry_if_exception(_is_retryable_http_error),
        reraise=True,
    ):
        with attempt_state:
            attempt += 1
            if on_attempt is not None:
                maybe = on_attempt(attempt)
                if maybe is not None:
                    await maybe
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                response = await client.request(
                    method,
                    url,
                    json=json,
                    params=params,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            if response.status_code >= 400:
                detail = _extract_detail(response)
                raise ToolError(
                    detail.get("code", "UPSTREAM_CLIENT_ERROR"),
                    detail.get("message", response.text),
                    retryable=False,
                    status_code=response.status_code,
                )
            return response
    msg = "request_with_retry exhausted without response"
    raise RuntimeError(msg)


def _extract_detail(response: httpx.Response) -> dict[str, str]:
    try:
        body = response.json()
    except ValueError:
        return {"code": "UPSTREAM_CLIENT_ERROR", "message": response.text}
    detail = body.get("detail", body)
    if isinstance(detail, dict):
        return {
            "code": str(detail.get("code", "UPSTREAM_CLIENT_ERROR")),
            "message": str(detail.get("message", response.text)),
        }
    return {"code": "UPSTREAM_CLIENT_ERROR", "message": str(detail)}


async def run_tool[TModel: BaseModel](
    *,
    name: str,
    args_model: type[TModel],
    raw_args: dict[str, Any],
    execute: Callable[[TModel], Awaitable[dict[str, Any]]],
    tracer: TraceRecorder | None = None,
    record_execution: bool = True,
) -> dict[str, Any]:
    """Validate args, execute tool, map errors, and record trace attempts.

    Args:
        name: Tool name.
        args_model: Pydantic model for arguments.
        raw_args: Raw argument dict from the LLM.
        execute: Async callable receiving validated args, returning tool_result.
        tracer: Optional trace recorder.
        record_execution: When False, only validation failures are traced
            (HTTP tools record each retry attempt themselves).

    Returns:
        dict[str, Any]: Unified tool result envelope.
    """
    started = time.perf_counter()
    attempt = 1
    try:
        validated = args_model.model_validate(raw_args)
    except ValidationError as exc:
        result = tool_result(
            ok=False,
            code="VALIDATION_ERROR",
            message=str(exc.errors()),
            retryable=False,
        )
        if tracer is not None:
            await tracer.record(
                node="tools",
                tool_name=name,
                input_data=raw_args,
                output_data=result,
                error=result["error"],
                attempt=attempt,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        return result

    try:
        result = await execute(validated)
    except ToolError as exc:
        result = tool_result(
            ok=False,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
        )
    except httpx.HTTPError as exc:
        logger.info("Tool %s upstream unavailable: %s", name, exc)
        result = tool_result(
            ok=False,
            code="UPSTREAM_UNAVAILABLE",
            message=str(exc),
            retryable=True,
        )
    except Exception as exc:  # noqa: BLE001 — map unexpected to envelope
        logger.exception("Tool %s unexpected error", name)
        result = tool_result(
            ok=False,
            code="INTERNAL_ERROR",
            message=str(exc),
            retryable=False,
        )

    if tracer is not None and record_execution:
        await tracer.record(
            node="tools",
            tool_name=name,
            input_data=validated.model_dump(mode="json"),
            output_data=result,
            error=result.get("error"),
            attempt=attempt,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
    return result

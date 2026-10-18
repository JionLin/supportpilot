"""Tests for the tool layer (validation, retry, schemas).

@author jiaolin
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.tools.base import idempotency_key
from app.tools.context import ToolContext
from app.tools.orders import get_order
from app.tools.registry import TOOL_HANDLERS, get_openai_tools_schema
from app.tools.shipping import track_shipment
from app.tracing import TraceRecorder, redact_pii


def test_openai_tools_schema_has_eight_tools() -> None:
    """Exported schema matches SPEC section 7 tool names."""
    schema = get_openai_tools_schema()
    names = [item["function"]["name"] for item in schema]
    assert names == [
        "search_knowledge_base",
        "get_order",
        "track_shipment",
        "create_return_request",
        "check_availability",
        "book_appointment",
        "upsert_crm_contact",
        "handoff_to_human",
    ]
    assert set(TOOL_HANDLERS) == set(names)
    for item in schema:
        assert item["type"] == "function"
        assert item["function"]["parameters"]["additionalProperties"] is False


def test_redact_pii_masks_email_and_phone() -> None:
    """Emails and phones are redacted in nested payloads."""
    payload = {
        "email": "jane@example.com",
        "note": "call +1-555-0100 please",
        "nested": ["alex@example.com"],
    }
    redacted = redact_pii(payload)
    assert redacted["email"] == "[REDACTED_EMAIL]"
    assert "[REDACTED_PHONE]" in redacted["note"]
    assert redacted["nested"] == ["[REDACTED_EMAIL]"]


def test_idempotency_key_stable() -> None:
    """Same conversation+payload yields the same key."""
    key_a = idempotency_key("conv-1", {"slot_id": "S1", "email": "a@b.com"})
    key_b = idempotency_key("conv-1", {"slot_id": "S1", "email": "a@b.com"})
    key_c = idempotency_key("conv-2", {"slot_id": "S1", "email": "a@b.com"})
    assert key_a == key_b
    assert key_a != key_c


@pytest.mark.asyncio
@respx.mock
async def test_get_order_success() -> None:
    """Successful order lookup returns ok envelope."""
    route = respx.get("http://mock.test/mock/orders/A1001").mock(
        return_value=httpx.Response(
            200,
            json={
                "order_id": "A1001",
                "email": "jane@example.com",
                "status": "in_transit",
                "tracking_number": "TRK1001",
            },
        )
    )
    tracer = TraceRecorder()
    ctx = ToolContext(
        conversation_id="00000000-0000-4000-8000-000000000001",
        tracer=tracer,
        mock_base_url="http://mock.test",
    )
    result = await get_order(
        {"order_id": "A1001", "email": "jane@example.com"},
        ctx,
    )
    assert result["ok"] is True
    assert result["data"]["order_id"] == "A1001"
    assert route.call_count == 1
    assert tracer.steps[-1]["tool_name"] == "get_order"
    assert ctx.verified_customer is not None


@pytest.mark.asyncio
@respx.mock
async def test_get_order_timeout_then_retry_success() -> None:
    """Timeouts are retried and eventually succeed."""
    route = respx.get("http://mock.test/mock/orders/A1001").mock(
        side_effect=[
            httpx.TimeoutException("timed out"),
            httpx.Response(
                200,
                json={
                    "order_id": "A1001",
                    "email": "jane@example.com",
                    "status": "in_transit",
                    "tracking_number": "TRK1001",
                },
            ),
        ]
    )
    tracer = TraceRecorder()
    ctx = ToolContext(
        conversation_id="c1",
        tracer=tracer,
        mock_base_url="http://mock.test",
    )
    result = await get_order(
        {"order_id": "A1001", "email": "jane@example.com"},
        ctx,
    )
    assert result["ok"] is True
    assert route.call_count == 2
    assert len(tracer.steps) == 2
    assert tracer.steps[0]["error"] is not None
    assert tracer.steps[1]["error"] is None


@pytest.mark.asyncio
@respx.mock
async def test_track_shipment_consecutive_5xx_fails() -> None:
    """Three 5xx responses exhaust retries and return UPSTREAM_UNAVAILABLE."""
    route = respx.get("http://mock.test/mock/shipping/TRK1001").mock(
        return_value=httpx.Response(503, json={"detail": "down"})
    )
    tracer = TraceRecorder()
    ctx = ToolContext(
        conversation_id="c1",
        tracer=tracer,
        mock_base_url="http://mock.test",
    )
    result = await track_shipment({"tracking_number": "TRK1001"}, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert result["error"]["retryable"] is True
    assert route.call_count == 3
    assert len(tracer.steps) == 3


@pytest.mark.asyncio
@respx.mock
async def test_get_order_4xx_does_not_retry() -> None:
    """Client errors are not retried."""
    route = respx.get("http://mock.test/mock/orders/A1001").mock(
        return_value=httpx.Response(
            404,
            json={"detail": {"code": "NOT_FOUND", "message": "Not found"}},
        )
    )
    tracer = TraceRecorder()
    ctx = ToolContext(
        conversation_id="c1",
        tracer=tracer,
        mock_base_url="http://mock.test",
    )
    result = await get_order(
        {"order_id": "A1001", "email": "jane@example.com"},
        ctx,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "ORDER_NOT_FOUND"
    assert route.call_count == 1
    assert len(tracer.steps) == 1


@pytest.mark.asyncio
async def test_get_order_validation_failure() -> None:
    """Invalid order_id pattern returns VALIDATION_ERROR without HTTP."""
    tracer = TraceRecorder()
    ctx = ToolContext(
        conversation_id="c1",
        tracer=tracer,
        mock_base_url="http://mock.test",
    )
    result = await get_order(
        {"order_id": "bad", "email": "jane@example.com"},
        ctx,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert len(tracer.steps) == 1

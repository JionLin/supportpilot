"""LangGraph agent tests using ScriptedFakeChatModel.

@author jiaolin
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.agent.fake_llm import ScriptedFakeChatModel, ai_text, ai_tool_call
from app.agent.graph import run_agent
from app.config import get_settings
from app.tools.kb import set_knowledge_retriever


@pytest.fixture(autouse=True)
def _wire_fake_kb() -> None:
    """Provide a tiny in-memory KB retriever for FAQ tests."""

    async def _retriever(query: str, top_k: int) -> list[dict[str, object]]:
        _ = top_k
        if "return" in query.lower() or "policy" in query.lower():
            return [
                {
                    "chunk_id": "chunk-1",
                    "document": "Return Policy",
                    "content": "Returns accepted within 30 days of delivery.",
                    "snippet": "Returns accepted within 30 days of delivery.",
                }
            ]
        return []

    set_knowledge_retriever(_retriever)
    yield
    set_knowledge_retriever(None)


@pytest.mark.asyncio
async def test_faq_flow_with_citations() -> None:
    """FAQ path: search_knowledge_base then final answer with citations."""
    model = ScriptedFakeChatModel(
        script=[
            ai_tool_call("search_knowledge_base", {"query": "return policy"}),
            ai_text(
                "You can return unused items within 30 days of delivery. "
                "[source: Return Policy]"
            ),
        ]
    )
    _, reply, _ = await run_agent(
        message="What is your return policy?",
        model=model,
    )
    assert reply.intent == "faq"
    assert reply.citations
    assert "30 days" in reply.answer


@pytest.mark.asyncio
@respx.mock
async def test_order_lookup_flow() -> None:
    """Order path: get_order then final answer with order card."""
    respx.get("http://127.0.0.1:8000/mock/orders/A1001").mock(
        return_value=httpx.Response(
            200,
            json={
                "order_id": "A1001",
                "email": "jane@example.com",
                "status": "in_transit",
                "tracking_number": "TRK1001",
                "items": [],
                "total_cents": 2900,
                "currency": "USD",
                "ordered_at": "2026-10-01T00:00:00+00:00",
                "delivered_at": None,
                "cancelled_at": None,
                "shipping_address": None,
            },
        )
    )
    model = ScriptedFakeChatModel(
        script=[
            ai_tool_call(
                "get_order",
                {"order_id": "A1001", "email": "jane@example.com"},
            ),
            ai_text("Order A1001 is in transit. Tracking TRK1001."),
        ]
    )
    _, reply, state = await run_agent(
        message="Where is order A1001? email jane@example.com",
        model=model,
    )
    assert reply.intent == "order_status"
    assert state.get("order_card") is not None
    assert "A1001" in reply.answer


@pytest.mark.asyncio
@respx.mock
async def test_return_flow() -> None:
    """Return path verifies order then creates RMA."""
    respx.get("http://127.0.0.1:8000/mock/orders/A1003").mock(
        return_value=httpx.Response(
            200,
            json={
                "order_id": "A1003",
                "email": "sam@example.com",
                "status": "delivered",
                "tracking_number": "TRK1003",
                "items": [{"sku": "SHOE-WHT-9"}],
                "total_cents": 8900,
                "currency": "USD",
                "ordered_at": "2026-10-10T00:00:00+00:00",
                "delivered_at": "2026-10-13T00:00:00+00:00",
                "cancelled_at": None,
                "shipping_address": None,
            },
        )
    )
    respx.post("http://127.0.0.1:8000/mock/returns").mock(
        return_value=httpx.Response(
            201,
            json={
                "rma_id": "RMA-TEST01",
                "order_id": "A1003",
                "item_skus": ["SHOE-WHT-9"],
                "reason": "changed_mind",
                "status": "open",
            },
        )
    )
    model = ScriptedFakeChatModel(
        script=[
            ai_tool_call(
                "get_order",
                {"order_id": "A1003", "email": "sam@example.com"},
            ),
            ai_tool_call(
                "create_return_request",
                {
                    "order_id": "A1003",
                    "item_skus": ["SHOE-WHT-9"],
                    "reason": "changed_mind",
                },
            ),
            ai_text("Created return RMA-TEST01 for your shoes."),
        ]
    )
    _, reply, _ = await run_agent(
        message="I want to return order A1003, sam@example.com, shoes",
        model=model,
    )
    assert reply.intent == "return"
    assert "RMA" in reply.answer.upper() or "return" in reply.answer.lower()


@pytest.mark.asyncio
@respx.mock
async def test_booking_flow() -> None:
    """Booking path checks availability then books a slot."""
    respx.get("http://127.0.0.1:8000/mock/calendar/slots").mock(
        return_value=httpx.Response(
            200,
            json={
                "timezone": "UTC",
                "slots": [
                    {
                        "slot_id": "SLOT-TEST",
                        "slot_start": "2026-10-20T10:00:00+00:00",
                        "slot_end": "2026-10-20T10:30:00+00:00",
                        "timezone": "UTC",
                    }
                ],
            },
        )
    )
    respx.post("http://127.0.0.1:8000/mock/calendar/bookings").mock(
        return_value=httpx.Response(
            201,
            json={
                "booking_id": "BK-TEST",
                "slot_id": "SLOT-TEST",
                "slot_start": "2026-10-20T10:00:00+00:00",
                "name": "Jane",
                "email": "jane@example.com",
            },
        )
    )
    model = ScriptedFakeChatModel(
        script=[
            ai_tool_call(
                "check_availability",
                {"date_from": "2026-10-20", "date_to": "2026-10-20"},
            ),
            ai_tool_call(
                "book_appointment",
                {
                    "slot_id": "SLOT-TEST",
                    "name": "Jane",
                    "email": "jane@example.com",
                    "topic": "Order help",
                },
            ),
            ai_text("Booked your call-back for SLOT-TEST (BK-TEST)."),
        ]
    )
    _, reply, _ = await run_agent(
        message="Book a call tomorrow for jane@example.com",
        model=model,
    )
    assert reply.intent == "booking"


@pytest.mark.asyncio
async def test_max_steps_triggers_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exceeding MAX_STEPS routes to handoff."""
    monkeypatch.setenv("MAX_STEPS", "1")
    get_settings.cache_clear()
    # step_count increments in agent; with max_steps=1 the second agent visit handoffs.
    model = ScriptedFakeChatModel(
        script=[
            ai_tool_call("search_knowledge_base", {"query": "x"}),
            ai_text("should not be reached as final without handoff"),
            ai_text("still looping"),
        ]
    )
    _, reply, state = await run_agent(message="loop please", model=model)
    get_settings.cache_clear()
    assert reply.needs_human is True or state.get("status") == "handed_off"
    assert reply.intent == "handoff"


@pytest.mark.asyncio
@respx.mock
async def test_tool_failures_trigger_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MAX_TOOL_ERRORS consecutive failures escalate to handoff."""
    monkeypatch.setenv("MAX_TOOL_ERRORS", "2")
    get_settings.cache_clear()
    respx.get(url__regex=r".*/mock/shipping/.*").mock(
        return_value=httpx.Response(503, json={"detail": "down"})
    )
    model = ScriptedFakeChatModel(
        script=[
            ai_tool_call("track_shipment", {"tracking_number": "TRK1001"}),
            ai_tool_call("track_shipment", {"tracking_number": "TRK1001"}),
            ai_text("should hand off before this"),
        ]
    )
    _, reply, state = await run_agent(message="track TRK1001", model=model)
    get_settings.cache_clear()
    assert state.get("tool_errors", 0) >= 2 or reply.needs_human
    assert reply.intent == "handoff" or reply.needs_human


@pytest.mark.asyncio
async def test_structured_output_fallback() -> None:
    """Non-JSON final text still yields a usable AgentReply via plain-text path."""
    model = ScriptedFakeChatModel(
        script=[ai_text("Here is a simple plain answer without JSON.")]
    )
    _, reply, _ = await run_agent(message="hi", model=model)
    assert reply.answer
    assert reply.confidence >= 0.3

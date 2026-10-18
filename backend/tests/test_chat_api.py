"""Integration tests for /api/chat with Fake LLM.

@author jiaolin
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agent.schemas import AgentReply
from app.config import get_settings
from app.db.session import reset_engine
from app.main import create_app


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    get_settings.cache_clear()
    reset_engine()
    yield
    get_settings.cache_clear()
    reset_engine()


@pytest.mark.asyncio
async def test_chat_json_with_fake_agent() -> None:
    """Non-SSE chat returns AgentReply JSON and persists conversation."""
    fake_reply = AgentReply(
        answer="Hello from fake agent",
        intent="other",
        confidence=0.8,
    )
    with patch(
        "app.api.chat.run_agent",
        new=AsyncMock(
            return_value=(
                "11111111-1111-4111-8111-111111111111",
                fake_reply,
                {"status": "active"},
            )
        ),
    ):
        application = create_app()
        transport = ASGITransport(app=application)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "conversation_id": "11111111-1111-4111-8111-111111111111",
                    "message": "Hello",
                },
            )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Hello from fake agent"
    assert payload["conversation_id"] == "11111111-1111-4111-8111-111111111111"


@pytest.mark.asyncio
async def test_chat_sse_emits_final_event() -> None:
    """SSE chat emits token/final events."""
    fake_reply = AgentReply(
        answer="Streamed answer here",
        intent="faq",
        confidence=0.9,
    )
    with patch(
        "app.api.chat.run_agent",
        new=AsyncMock(
            return_value=(
                "22222222-2222-4222-8222-222222222222",
                fake_reply,
                {"status": "active"},
            )
        ),
    ):
        application = create_app()
        transport = ASGITransport(app=application)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            async with client.stream(
                "POST",
                "/api/chat",
                json={"message": "Hi"},
                headers={"Accept": "text/event-stream"},
            ) as response:
                assert response.status_code == 200
                body = ""
                async for chunk in response.aiter_text():
                    body += chunk
    assert "event: final" in body
    assert "Streamed answer here" in body


@pytest.mark.asyncio
async def test_tickets_and_conversations_list() -> None:
    """Tickets and conversations endpoints respond."""
    application = create_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tickets = await client.get("/api/tickets")
        assert tickets.status_code == 200
        assert "tickets" in tickets.json()
        conversations = await client.get("/api/conversations")
        assert conversations.status_code == 200
        assert "items" in conversations.json()
        appointments = await client.get("/api/appointments")
        assert appointments.status_code == 200

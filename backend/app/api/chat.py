"""Chat REST + SSE endpoints.

@author jiaolin
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_agent_graph, run_agent
from app.agent.schemas import AgentReply
from app.db.session import get_async_session, get_session_factory
from app.services.conversations import get_or_create_conversation, persist_agent_turn
from app.services.webhook import post_webhook

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Incoming chat message."""

    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=4000)


def _wants_sse(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/event-stream" in accept


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """Run one agent turn; stream SSE when Accept requests it.

    Args:
        body: Chat request.
        request: Incoming HTTP request (for Accept header).
        session: DB session.

    Returns:
        Any: AgentReply JSON or SSE stream.
    """
    conversation = await get_or_create_conversation(session, body.conversation_id)
    await session.commit()

    graph = build_agent_graph(session_factory=get_session_factory())

    if _wants_sse(request):
        return StreamingResponse(
            _stream_chat(
                message=body.message,
                conversation_id=str(conversation.id),
                prior_status=conversation.status,
                graph=graph,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Conversation-Id": str(conversation.id),
            },
        )

    conv_id, reply, state = await run_agent(
        message=body.message,
        conversation_id=str(conversation.id),
        graph=graph,
        session_factory=get_session_factory(),
        prior_status=conversation.status or "active",
        prior_ticket_id=None,
    )
    # Reload conversation in this session
    conversation = await get_or_create_conversation(session, uuid.UUID(conv_id))
    await persist_agent_turn(
        session,
        conversation=conversation,
        user_message=body.message,
        reply=reply,
        state=state,
    )
    await _maybe_webhook(reply, state)
    payload = reply.model_dump(mode="json")
    payload["conversation_id"] = conv_id
    return JSONResponse(payload)


async def _stream_chat(
    *,
    message: str,
    conversation_id: str,
    prior_status: str | None,
    graph: Any,
) -> AsyncIterator[str]:
    try:
        yield _sse("token", {"text": ""})
        conv_id, reply, state = await run_agent(
            message=message,
            conversation_id=conversation_id,
            graph=graph,
            session_factory=get_session_factory(),
            prior_status=prior_status or "active",
        )
        # Emit tool events from actions
        for action in reply.actions:
            yield _sse(
                "tool_end",
                {
                    "tool": action.tool,
                    "status": action.status,
                    "summary": action.summary,
                },
            )
        for citation in reply.citations:
            yield _sse("citation", citation.model_dump(mode="json"))
        # Tokenize answer coarsely for streaming UX
        chunk_size = 24
        answer = reply.answer
        for index in range(0, len(answer), chunk_size):
            yield _sse("token", {"text": answer[index : index + chunk_size]})
        yield _sse(
            "final",
            {
                **reply.model_dump(mode="json"),
                "conversation_id": conv_id,
            },
        )

        session_factory = get_session_factory()
        async with session_factory() as session:
            conversation = await get_or_create_conversation(
                session, uuid.UUID(conv_id)
            )
            await persist_agent_turn(
                session,
                conversation=conversation,
                user_message=message,
                reply=reply,
                state=state,
            )
        await _maybe_webhook(reply, state)
    except Exception as exc:  # noqa: BLE001 — surface as SSE error
        yield _sse(
            "error",
            {"code": "CHAT_ERROR", "message": str(exc)},
        )


async def _maybe_webhook(reply: AgentReply, state: dict[str, Any]) -> None:
    if reply.needs_human or reply.ticket_id:
        await post_webhook(
            "handoff",
            {
                "ticket_id": reply.ticket_id,
                "answer": reply.answer,
                "intent": reply.intent,
            },
        )
    for action in reply.actions:
        if action.tool == "book_appointment" and action.status == "success":
            await post_webhook(
                "booking",
                {"summary": action.summary, "order_card": reply.order_card},
            )
    _ = state

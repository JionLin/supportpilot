"""Conversation and message persistence helpers.

@author jiaolin
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.schemas import AgentReply
from app.db.models import Conversation, Message, TraceStep
from app.tracing import TraceRecorder


async def get_or_create_conversation(
    session: AsyncSession,
    conversation_id: uuid.UUID | None,
) -> Conversation:
    """Load an existing conversation or create a new one.

    Args:
        session: DB session.
        conversation_id: Optional existing id.

    Returns:
        Conversation: Loaded or created row.
    """
    if conversation_id is not None:
        result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing
    conversation = Conversation(id=conversation_id or uuid.uuid4(), status="active")
    session.add(conversation)
    await session.flush()
    return conversation


async def add_message(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    role: str,
    content: str | None,
    structured: dict[str, Any] | None = None,
) -> Message:
    """Persist a message row.

    Args:
        session: DB session.
        conversation_id: Parent conversation.
        role: user/assistant/tool/system.
        content: Text content.
        structured: Optional structured payload.

    Returns:
        Message: Created message.
    """
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        structured=structured,
    )
    session.add(message)
    await session.flush()
    return message


async def persist_agent_turn(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_message: str,
    reply: AgentReply,
    state: dict[str, Any],
    tracer: TraceRecorder | None = None,
) -> None:
    """Persist user + assistant messages and optional trace steps.

    Args:
        session: DB session.
        conversation: Conversation row.
        user_message: User text.
        reply: Structured agent reply.
        state: Final graph state.
        tracer: Optional in-memory tracer to flush.
    """
    await add_message(
        session,
        conversation_id=conversation.id,
        role="user",
        content=user_message,
    )
    await add_message(
        session,
        conversation_id=conversation.id,
        role="assistant",
        content=reply.answer,
        structured=reply.model_dump(mode="json"),
    )
    if reply.needs_human or state.get("status") == "handed_off":
        conversation.status = "handed_off"
    if reply.ticket_id and state.get("verified_customer"):
        email = (state.get("verified_customer") or {}).get("email")
        if email:
            conversation.customer_email = str(email)

    if tracer is not None:
        for step in tracer.steps:
            session.add(
                TraceStep(
                    conversation_id=conversation.id,
                    run_id=tracer.run_id,
                    step_no=int(step["step_no"]),
                    node=str(step["node"]),
                    tool_name=step.get("tool_name"),
                    input=step.get("input"),
                    output=step.get("output"),
                    error=step.get("error"),
                    attempt=step.get("attempt") or 1,
                    latency_ms=step.get("latency_ms"),
                    prompt_tokens=step.get("prompt_tokens"),
                    completion_tokens=step.get("completion_tokens"),
                )
            )
    await session.commit()

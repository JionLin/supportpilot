"""Conversation list/detail/trace endpoints.

@author jiaolin
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, TraceStep
from app.db.session import get_async_session

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """List conversations newest-first.

    Args:
        limit: Page size.
        offset: Page offset.
        session: DB session.

    Returns:
        dict[str, Any]: Paginated conversation list.
    """
    total = await session.scalar(select(func.count()).select_from(Conversation)) or 0
    result = await session.execute(
        select(Conversation)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.scalars().all()
    return {
        "total": int(total),
        "items": [
            {
                "id": str(row.id),
                "status": row.status,
                "customer_email": row.customer_email,
                "channel": row.channel,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ],
    }


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Return conversation metadata and messages.

    Args:
        conversation_id: Conversation UUID.
        session: DB session.

    Returns:
        dict[str, Any]: Conversation detail.
    """
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Conversation not found"},
        )
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
    )
    messages = result.scalars().all()
    return {
        "id": str(conversation.id),
        "status": conversation.status,
        "customer_email": conversation.customer_email,
        "channel": conversation.channel,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "structured": msg.structured,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ],
    }


@router.get("/{conversation_id}/trace")
async def get_trace(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Return execution trace steps for a conversation.

    Args:
        conversation_id: Conversation UUID.
        session: DB session.

    Returns:
        dict[str, Any]: Trace step list.
    """
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Conversation not found"},
        )
    result = await session.execute(
        select(TraceStep)
        .where(TraceStep.conversation_id == conversation_id)
        .order_by(TraceStep.id.asc())
    )
    steps = result.scalars().all()
    return {
        "conversation_id": str(conversation_id),
        "steps": [
            {
                "id": step.id,
                "run_id": str(step.run_id),
                "step_no": step.step_no,
                "node": step.node,
                "tool_name": step.tool_name,
                "input": step.input,
                "output": step.output,
                "error": step.error,
                "attempt": step.attempt,
                "latency_ms": step.latency_ms,
                "prompt_tokens": step.prompt_tokens,
                "completion_tokens": step.completion_tokens,
                "created_at": step.created_at.isoformat() if step.created_at else None,
            }
            for step in steps
        ],
    }

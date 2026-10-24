"""Human handoff ticket endpoints.

@author jiaolin
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket
from app.db.session import get_async_session

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


class TicketUpdate(BaseModel):
    """Ticket status update payload."""

    status: Literal["open", "in_progress", "resolved"]


@router.get("")
async def list_tickets(
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """List handoff tickets.

    Args:
        status: Optional status filter.
        session: DB session.

    Returns:
        dict[str, Any]: Ticket list.
    """
    statement = select(Ticket).order_by(Ticket.created_at.desc())
    if status:
        statement = statement.where(Ticket.status == status)
    result = await session.execute(statement)
    rows = result.scalars().all()
    return {
        "tickets": [
            {
                "id": row.id,
                "conversation_id": str(row.conversation_id)
                if row.conversation_id
                else None,
                "reason": row.reason,
                "summary": row.summary,
                "priority": row.priority,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@router.patch("/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    body: TicketUpdate,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Update a ticket status.

    Args:
        ticket_id: Ticket id.
        body: Status update.
        session: DB session.

    Returns:
        dict[str, Any]: Updated ticket.
    """
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Ticket not found"},
        )
    ticket.status = body.status
    await session.commit()
    return {
        "id": ticket.id,
        "status": ticket.status,
        "reason": ticket.reason,
        "summary": ticket.summary,
        "priority": ticket.priority,
    }

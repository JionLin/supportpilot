"""Appointment list endpoint.

@author jiaolin
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Appointment
from app.db.session import get_async_session

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.get("")
async def list_appointments(
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """List booked appointments.

    Args:
        session: DB session.

    Returns:
        dict[str, Any]: Appointment list.
    """
    result = await session.execute(
        select(Appointment).order_by(Appointment.created_at.desc())
    )
    rows = result.scalars().all()
    return {
        "appointments": [
            {
                "id": row.id,
                "conversation_id": str(row.conversation_id)
                if row.conversation_id
                else None,
                "slot_start": row.slot_start.isoformat() if row.slot_start else None,
                "name": row.name,
                "email": row.email,
                "topic": row.topic,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }

"""handoff_to_human tool adapter.

@author jiaolin
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket
from app.tools.base import run_tool, tool_result
from app.tools.context import ToolContext
from app.tools.schemas import HandoffToHumanArgs


async def _next_ticket_id(session: AsyncSession) -> str:
    """Allocate a human-readable ticket id for today.

    Args:
        session: Async DB session.

    Returns:
        str: Ticket id like T-20261018-0001.
    """
    today = datetime.now(UTC).strftime("%Y%m%d")
    prefix = f"T-{today}-"
    result = await session.execute(
        select(func.count()).select_from(Ticket).where(Ticket.id.like(f"{prefix}%"))
    )
    count = int(result.scalar_one() or 0)
    return f"{prefix}{count + 1:04d}"


async def handoff_to_human(
    raw_args: dict[str, Any], ctx: ToolContext
) -> dict[str, Any]:
    """Create a human handoff ticket.

    Args:
        raw_args: Raw LLM tool arguments.
        ctx: Tool invocation context.

    Returns:
        dict[str, Any]: Unified tool result with ticket_id.
    """

    async def _execute(args: HandoffToHumanArgs) -> dict[str, Any]:
        session: AsyncSession | None = ctx.db_session
        if session is None:
            ticket_id = f"T-LOCAL-{args.reason[:4].upper()}-0001"
            ctx.handoff_ticket_id = ticket_id
            payload = {
                "ticket_id": ticket_id,
                "reason": args.reason,
                "summary": args.summary,
                "priority": args.priority,
                "eta_minutes": 30,
            }
            if ctx.tracer is not None:
                await ctx.tracer.record(
                    node="tools",
                    tool_name="handoff_to_human",
                    input_data=args.model_dump(mode="json"),
                    output_data=payload,
                    attempt=1,
                )
            return tool_result(ok=True, data=payload)

        ticket_id = await _next_ticket_id(session)
        session.add(
            Ticket(
                id=ticket_id,
                conversation_id=ctx.conversation_uuid,
                reason=args.reason,
                summary=args.summary,
                priority=args.priority,
                status="open",
            )
        )
        await session.flush()
        ctx.handoff_ticket_id = ticket_id
        payload = {
            "ticket_id": ticket_id,
            "reason": args.reason,
            "summary": args.summary,
            "priority": args.priority,
            "eta_minutes": 30,
        }
        if ctx.tracer is not None:
            await ctx.tracer.record(
                node="tools",
                tool_name="handoff_to_human",
                input_data=args.model_dump(mode="json"),
                output_data=payload,
                attempt=1,
            )
        return tool_result(ok=True, data=payload)

    return await run_tool(
        name="handoff_to_human",
        args_model=HandoffToHumanArgs,
        raw_args=raw_args,
        execute=_execute,
        tracer=ctx.tracer,
        record_execution=False,
    )

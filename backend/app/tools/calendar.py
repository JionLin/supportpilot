"""Calendar availability and booking tool adapters.

@author jiaolin
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Appointment
from app.tools.base import ToolError, idempotency_key, run_tool, tool_result
from app.tools.context import ToolContext
from app.tools.http_client import http_json
from app.tools.schemas import BookAppointmentArgs, CheckAvailabilityArgs


async def check_availability(
    raw_args: dict[str, Any], ctx: ToolContext
) -> dict[str, Any]:
    """List open call-back slots.

    Args:
        raw_args: Raw LLM tool arguments.
        ctx: Tool invocation context.

    Returns:
        dict[str, Any]: Unified tool result.
    """

    async def _execute(args: CheckAvailabilityArgs) -> dict[str, Any]:
        url = f"{ctx.mock_base_url.rstrip('/')}/mock/calendar/slots"
        try:
            data = await http_json(
                "GET",
                url,
                tool_name="check_availability",
                params={
                    "date_from": args.date_from,
                    "date_to": args.date_to,
                    "timezone": args.timezone,
                },
                tracer=ctx.tracer,
                input_for_trace=args.model_dump(mode="json"),
            )
        except httpx.HTTPError as exc:
            return tool_result(
                ok=False,
                code="UPSTREAM_UNAVAILABLE",
                message=str(exc),
                retryable=True,
            )
        return tool_result(ok=True, data=data)

    return await run_tool(
        name="check_availability",
        args_model=CheckAvailabilityArgs,
        raw_args=raw_args,
        execute=_execute,
        tracer=ctx.tracer,
        record_execution=False,
    )


async def book_appointment(
    raw_args: dict[str, Any], ctx: ToolContext
) -> dict[str, Any]:
    """Book a confirmed call-back slot (idempotent per conversation).

    Args:
        raw_args: Raw LLM tool arguments.
        ctx: Tool invocation context.

    Returns:
        dict[str, Any]: Unified tool result.
    """

    async def _execute(args: BookAppointmentArgs) -> dict[str, Any]:
        key = idempotency_key(
            ctx.conversation_id,
            {
                "slot_id": args.slot_id,
                "email": str(args.email),
                "name": args.name,
            },
        )
        url = f"{ctx.mock_base_url.rstrip('/')}/mock/calendar/bookings"
        body = {
            "slot_id": args.slot_id,
            "name": args.name,
            "email": str(args.email),
            "topic": args.topic,
        }
        try:
            data = await http_json(
                "POST",
                url,
                tool_name="book_appointment",
                json_body=body,
                tracer=ctx.tracer,
                input_for_trace={
                    **args.model_dump(mode="json"),
                    "idempotency_key": key,
                },
            )
        except ToolError as exc:
            return tool_result(
                ok=False,
                code=exc.code,
                message=exc.message,
                retryable=False,
            )
        except httpx.HTTPError as exc:
            return tool_result(
                ok=False,
                code="UPSTREAM_UNAVAILABLE",
                message=str(exc),
                retryable=True,
            )

        session: AsyncSession | None = ctx.db_session
        if session is not None:
            appointment_id = data.get("booking_id") or f"APPT-{key[:10].upper()}"
            slot_start_raw = data.get("slot_start")
            slot_start = (
                datetime.fromisoformat(slot_start_raw)
                if isinstance(slot_start_raw, str)
                else None
            )
            session.add(
                Appointment(
                    id=str(appointment_id),
                    conversation_id=ctx.conversation_uuid,
                    slot_start=slot_start,
                    name=args.name,
                    email=str(args.email),
                    topic=args.topic,
                )
            )
            await session.flush()
        data = {**data, "idempotency_key": key, "local_id": data.get("booking_id")}
        return tool_result(ok=True, data=data)

    return await run_tool(
        name="book_appointment",
        args_model=BookAppointmentArgs,
        raw_args=raw_args,
        execute=_execute,
        tracer=ctx.tracer,
        record_execution=False,
    )


def new_local_appointment_id() -> str:
    """Generate a fallback appointment id.

    Returns:
        str: Appointment id.
    """
    return f"APPT-{uuid4().hex[:10].upper()}"

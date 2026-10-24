"""Tool handler registry and schema export.

@author jiaolin
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.tools import calendar, crm, handoff, kb, orders, returns, shipping
from app.tools.context import ToolContext
from app.tools.schemas import get_openai_tools_schema

ToolHandler = Callable[[dict[str, Any], ToolContext], Awaitable[dict[str, Any]]]

TOOL_HANDLERS: dict[str, ToolHandler] = {
    "search_knowledge_base": kb.search_knowledge_base,
    "get_order": orders.get_order,
    "track_shipment": shipping.track_shipment,
    "create_return_request": returns.create_return_request,
    "check_availability": calendar.check_availability,
    "book_appointment": calendar.book_appointment,
    "upsert_crm_contact": crm.upsert_crm_contact,
    "handoff_to_human": handoff.handoff_to_human,
}


async def dispatch_tool(
    name: str,
    raw_args: dict[str, Any],
    ctx: ToolContext,
) -> dict[str, Any]:
    """Dispatch a tool call by name.

    Args:
        name: Tool function name.
        raw_args: Raw arguments.
        ctx: Tool context.

    Returns:
        dict[str, Any]: Unified tool result.
    """
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {
            "ok": False,
            "data": None,
            "error": {
                "code": "UNKNOWN_TOOL",
                "message": f"Unknown tool: {name}",
                "retryable": False,
            },
        }
    return await handler(raw_args, ctx)


__all__ = ["TOOL_HANDLERS", "dispatch_tool", "get_openai_tools_schema"]

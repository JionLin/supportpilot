"""Tools execution node wrapping the tool registry.

@author jiaolin
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.schemas import Citation
from app.agent.state import AgentState
from app.config import get_settings
from app.tools.context import ToolContext
from app.tools.registry import dispatch_tool
from app.tracing import TraceRecorder


def make_tools_node(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> Callable[[AgentState], Awaitable[dict[str, Any]]]:
    """Create a tools node with optional DB session factory.

    Args:
        session_factory: Optional async session factory for write tools.

    Returns:
        Callable: Async LangGraph node.
    """

    async def tools_node(state: AgentState) -> dict[str, Any]:
        """Execute tool calls from the latest AI message.

        Args:
            state: Current agent state.

        Returns:
            dict[str, Any]: Tool messages and bookkeeping updates.
        """
        settings = get_settings()
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {}

        async def _run(session: AsyncSession | None) -> dict[str, Any]:
            tracer = TraceRecorder(conversation_id=None, session=None)
            ctx = ToolContext(
                conversation_id=state.get("conversation_id") or "unknown",
                tracer=tracer,
                mock_base_url=settings.mock_base_url,
                verified_customer=state.get("verified_customer"),
                db_session=session,
                citations=[
                    c.model_dump() if isinstance(c, Citation) else dict(c)
                    for c in (state.get("citations") or [])
                ],
            )

            tool_messages: list[ToolMessage] = []
            actions = list(state.get("actions") or [])
            tool_errors = int(state.get("tool_errors") or 0)
            order_card = state.get("order_card")
            ticket_id = state.get("ticket_id")
            handoff_reason = state.get("handoff_reason")
            handoff_summary = state.get("handoff_summary")

            for call in last.tool_calls:
                name = call["name"]
                args = call.get("args") or {}
                call_id = call.get("id") or name
                result = await dispatch_tool(name, args, ctx)
                ok = bool(result.get("ok"))
                actions.append(
                    {
                        "tool": name,
                        "status": "success" if ok else "failed",
                        "summary": _summarize(result),
                    }
                )
                if not ok:
                    tool_errors += 1
                if name == "get_order" and ok and isinstance(result.get("data"), dict):
                    order_card = result["data"]
                if name == "handoff_to_human" and ok:
                    data = result.get("data") or {}
                    ticket_id = data.get("ticket_id")
                    handoff_reason = args.get("reason") or "other"
                    handoff_summary = args.get("summary") or ""

                tool_messages.append(
                    ToolMessage(
                        content=json.dumps(result),
                        tool_call_id=call_id,
                        name=name,
                    )
                )

            citations = [
                Citation.model_validate(item) if isinstance(item, dict) else item
                for item in ctx.citations
            ]
            update: dict[str, Any] = {
                "messages": tool_messages,
                "actions": actions,
                "tool_errors": tool_errors,
                "citations": citations,
                "verified_customer": ctx.verified_customer,
                "order_card": order_card,
                "ticket_id": ticket_id or ctx.handoff_ticket_id,
            }
            if handoff_reason:
                update["handoff_reason"] = handoff_reason
            if handoff_summary:
                update["handoff_summary"] = handoff_summary
            if session is not None:
                await session.commit()
            return update

        if session_factory is None:
            return await _run(None)
        async with session_factory() as session:
            return await _run(session)

    return tools_node


def _summarize(result: dict[str, Any]) -> str:
    if result.get("ok"):
        data = result.get("data")
        if isinstance(data, dict):
            for key in ("rma_id", "ticket_id", "booking_id", "order_id", "count"):
                if key in data:
                    return f"{key}={data[key]}"
        return "ok"
    error = result.get("error") or {}
    return str(error.get("code") or "error")

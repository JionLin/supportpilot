"""Handoff node: ensure ticket exists and mark conversation handed_off.

@author jiaolin
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.schemas import ActionRecord, AgentReply, Citation
from app.agent.state import AgentState
from app.tools.context import ToolContext
from app.tools.handoff import handoff_to_human


def make_handoff_node(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> Callable[[AgentState], Awaitable[dict[str, Any]]]:
    """Create a handoff node.

    Args:
        session_factory: Optional DB session factory.

    Returns:
        Callable: Async LangGraph node.
    """

    async def handoff_node(state: AgentState) -> dict[str, Any]:
        """Create a ticket if needed and emit a handoff AgentReply.

        Args:
            state: Current agent state.

        Returns:
            dict[str, Any]: Status + final reply update.
        """
        ticket_id = state.get("ticket_id")
        reason = state.get("handoff_reason") or "other"
        summary = state.get("handoff_summary") or "Automated handoff"

        if ticket_id is None:

            async def _create(session: AsyncSession | None) -> str | None:
                ctx = ToolContext(
                    conversation_id=state.get("conversation_id") or "unknown",
                    db_session=session,
                )
                mapped_reason = (
                    reason
                    if reason
                    in {
                        "customer_request",
                        "negative_sentiment",
                        "out_of_policy",
                        "low_confidence",
                        "tool_failure",
                        "other",
                    }
                    else "other"
                )
                result = await handoff_to_human(
                    {
                        "reason": mapped_reason,
                        "summary": summary,
                        "priority": "normal",
                    },
                    ctx,
                )
                if session is not None:
                    await session.commit()
                if result.get("ok"):
                    return (result.get("data") or {}).get("ticket_id")
                return None

            if session_factory is None:
                ticket_id = await _create(None)
            else:
                async with session_factory() as session:
                    ticket_id = await _create(session)

        answer = (
            f"I've connected you with a human agent. Your ticket is {ticket_id}. "
            "Someone should follow up within about 30 minutes."
            if ticket_id
            else "I've escalated your request to a human agent."
        )
        actions: list[ActionRecord] = []
        for item in state.get("actions") or []:
            if isinstance(item, ActionRecord):
                actions.append(item)
            elif isinstance(item, dict):
                actions.append(ActionRecord.model_validate(item))
        citations: list[Citation] = []
        raw_citations: list[Any] = list(state.get("citations") or [])
        for item in raw_citations:
            if isinstance(item, Citation):
                citations.append(item)
            elif isinstance(item, dict):
                citations.append(Citation.model_validate(item))
        reply = AgentReply(
            answer=answer,
            intent="handoff",
            actions=actions,
            citations=citations,
            order_card=state.get("order_card"),
            needs_human=True,
            ticket_id=ticket_id,
            confidence=0.9,
        )
        return {
            "status": "handed_off",
            "ticket_id": ticket_id,
            "final": reply,
            "messages": [AIMessage(content=reply.answer)],
        }

    return handoff_node

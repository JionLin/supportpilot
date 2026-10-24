"""LangGraph agent state definition.

@author jiaolin
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.agent.schemas import AgentReply, Citation


class AgentState(TypedDict, total=False):
    """Mutable state flowing through the support agent graph."""

    conversation_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    step_count: int
    tool_errors: int
    citations: list[Citation]
    verified_customer: dict[str, Any] | None
    status: Literal["active", "handed_off", "closed"]
    final: AgentReply | None
    risk_flags: list[str]
    actions: list[dict[str, Any]]
    handoff_reason: str | None
    handoff_summary: str | None
    ticket_id: str | None
    order_card: dict[str, Any] | None

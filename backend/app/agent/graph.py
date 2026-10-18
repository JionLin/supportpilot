"""Compile and run the SupportPilot LangGraph agent.

@author jiaolin
"""

from __future__ import annotations

import logging
from typing import Any, Literal
from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.llm import bind_tools, build_chat_model
from app.agent.nodes.agent_node import make_agent_node
from app.agent.nodes.finalize import make_finalize_node
from app.agent.nodes.guard import guard_node
from app.agent.nodes.handoff_node import make_handoff_node
from app.agent.nodes.tools_node import make_tools_node
from app.agent.schemas import AgentReply
from app.agent.state import AgentState
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _route_after_guard(state: AgentState) -> Literal["agent", "finalize"]:
    if state.get("final") is not None:
        return "finalize"
    return "agent"


def _route_after_agent(
    state: AgentState,
) -> Literal["tools", "finalize", "handoff"]:
    settings = get_settings()
    if state.get("handoff_reason"):
        return "handoff"
    if int(state.get("step_count") or 0) > settings.max_steps:
        return "handoff"
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and last.tool_calls:
        # Escalation tool short-circuits after tools execute; still go tools first.
        return "tools"
    return "finalize"


def _route_after_tools(
    state: AgentState,
) -> Literal["agent", "handoff"]:
    settings = get_settings()
    if state.get("ticket_id") and state.get("handoff_reason"):
        return "handoff"
    # handoff_to_human was called
    actions = state.get("actions") or []
    if any(
        isinstance(a, dict)
        and a.get("tool") == "handoff_to_human"
        and a.get("status") == "success"
        for a in actions
    ):
        return "handoff"
    if int(state.get("tool_errors") or 0) >= settings.max_tool_errors:
        return "handoff"
    if int(state.get("step_count") or 0) >= settings.max_steps:
        return "handoff"
    return "agent"


def build_agent_graph(
    *,
    model: BaseChatModel | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    checkpointer: Any | None = None,
    settings: Settings | None = None,
) -> Any:
    """Build and compile the support agent StateGraph.

    Args:
        model: Optional chat model (Fake or real). Tools are bound here.
        session_factory: Optional DB session factory for write tools.
        checkpointer: Optional LangGraph checkpointer (MemorySaver default).
        settings: Optional settings override.

    Returns:
        CompiledStateGraph: Runnable agent graph.
    """
    _ = settings or get_settings()
    base_model = model or build_chat_model()
    tool_model = bind_tools(base_model)

    graph = StateGraph(AgentState)
    graph.add_node("guard", guard_node)
    graph.add_node("agent", make_agent_node(tool_model))  # type: ignore[arg-type]
    graph.add_node("tools", make_tools_node(session_factory))  # type: ignore[arg-type]
    graph.add_node("finalize", make_finalize_node(base_model))  # type: ignore[arg-type]
    graph.add_node("handoff", make_handoff_node(session_factory))  # type: ignore[arg-type]

    graph.add_edge(START, "guard")
    graph.add_conditional_edges(
        "guard",
        _route_after_guard,
        {"agent": "agent", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "agent",
        _route_after_agent,
        {"tools": "tools", "finalize": "finalize", "handoff": "handoff"},
    )
    graph.add_conditional_edges(
        "tools",
        _route_after_tools,
        {"agent": "agent", "handoff": "handoff"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("handoff", END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return graph.compile(checkpointer=saver)


async def run_agent(
    *,
    message: str,
    conversation_id: str | None = None,
    graph: Any | None = None,
    model: BaseChatModel | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    prior_status: str = "active",
    prior_ticket_id: str | None = None,
) -> tuple[str, AgentReply, dict[str, Any]]:
    """Run one user turn through the agent graph.

    Args:
        message: User message text.
        conversation_id: Optional conversation id (generated when missing).
        graph: Optional pre-built graph.
        model: Optional model override when building a graph.
        session_factory: Optional DB session factory.
        prior_status: Existing conversation status.
        prior_ticket_id: Existing ticket id when handed off.

    Returns:
        tuple: (conversation_id, AgentReply, raw final state)
    """
    conv_id = conversation_id or str(uuid4())
    compiled = graph or build_agent_graph(
        model=model,
        session_factory=session_factory,
    )
    initial: AgentState = {
        "conversation_id": conv_id,
        "messages": [HumanMessage(content=message)],
        "step_count": 0,
        "tool_errors": 0,
        "citations": [],
        "verified_customer": None,
        "status": prior_status,  # type: ignore[typeddict-item]
        "final": None,
        "risk_flags": [],
        "actions": [],
        "ticket_id": prior_ticket_id,
    }
    config = {"configurable": {"thread_id": conv_id}}
    result = await compiled.ainvoke(initial, config=config)
    final = result.get("final")
    if not isinstance(final, AgentReply):
        final = AgentReply(
            answer="Something went wrong generating a reply.",
            intent="other",
            confidence=0.2,
        )
    return conv_id, final, result

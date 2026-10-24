"""Input guard node: length limits, injection heuristics, handed-off short-circuit.

@author jiaolin
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.schemas import AgentReply
from app.agent.state import AgentState

_MAX_INPUT_CHARS = 4000
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(your|the)\s+system\s+prompt", re.I),
    re.compile(r"you\s+are\s+now\s+DAN", re.I),
]


def guard_node(state: AgentState) -> dict[str, Any]:
    """Validate the latest user message and short-circuit when handed off.

    Args:
        state: Current agent state.

    Returns:
        dict[str, Any]: Partial state update.
    """
    if state.get("status") == "handed_off":
        ticket = state.get("ticket_id") or "pending"
        reply = AgentReply(
            answer=(
                f"This conversation was handed off to a human agent "
                f"(ticket {ticket}). Please wait for a follow-up."
            ),
            intent="handoff",
            needs_human=True,
            ticket_id=ticket if ticket != "pending" else None,
            confidence=1.0,
        )
        return {
            "final": reply,
            "messages": [AIMessage(content=reply.answer)],
        }

    messages = state.get("messages") or []
    latest = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)),
        None,
    )
    if latest is None:
        return {"risk_flags": ["missing_user_message"]}

    content = latest.content if isinstance(latest.content, str) else str(latest.content)
    flags: list[str] = list(state.get("risk_flags") or [])
    if len(content) > _MAX_INPUT_CHARS:
        truncated = content[:_MAX_INPUT_CHARS]
        flags.append("input_truncated")
        return {
            "risk_flags": flags,
            "messages": [HumanMessage(content=truncated)],
        }

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(content):
            flags.append("prompt_injection_suspected")
            break

    return {"risk_flags": flags}

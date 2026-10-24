"""Finalize node: parse structured AgentReply or fall back.

@author jiaolin
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.schemas import ActionRecord, AgentReply, Citation
from app.agent.state import AgentState

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def make_finalize_node(
    model: BaseChatModel | None = None,
) -> Callable[[AgentState], Awaitable[dict[str, Any]]]:
    """Create a finalize node with optional structured-output retry model.

    Args:
        model: Optional chat model for structured-output retry.

    Returns:
        Callable: Async LangGraph node.
    """

    async def finalize_node(state: AgentState) -> dict[str, Any]:
        """Produce the structured AgentReply for the user.

        Args:
            state: Current agent state.

        Returns:
            dict[str, Any]: Final reply update.
        """
        if state.get("final") is not None:
            return {}

        messages = state.get("messages") or []
        last_ai = next(
            (
                m
                for m in reversed(messages)
                if isinstance(m, AIMessage) and not m.tool_calls
            ),
            None,
        )
        raw = ""
        if last_ai is not None:
            raw = (
                last_ai.content
                if isinstance(last_ai.content, str)
                else str(last_ai.content)
            )

        reply = _try_parse_reply(raw, state)
        if reply is None and model is not None and raw:
            reply = await _structured_retry(model, raw, state)
        if reply is None:
            reply = AgentReply(
                answer=raw
                or (
                    "Sorry — I had trouble formatting a response. "
                    "A human can help next."
                ),
                intent=_guess_intent(state),
                actions=_actions_from_state(state),
                citations=list(state.get("citations") or []),
                order_card=state.get("order_card"),
                needs_human=bool(state.get("ticket_id")),
                ticket_id=state.get("ticket_id"),
                confidence=0.3,
            )

        return {"final": reply, "messages": [AIMessage(content=reply.answer)]}

    return finalize_node


def _actions_from_state(state: AgentState) -> list[ActionRecord]:
    actions: list[ActionRecord] = []
    for item in state.get("actions") or []:
        if isinstance(item, ActionRecord):
            actions.append(item)
        elif isinstance(item, dict):
            actions.append(ActionRecord.model_validate(item))
    return actions


def _guess_intent(
    state: AgentState,
) -> Literal[
    "faq",
    "order_status",
    "return",
    "booking",
    "lead",
    "handoff",
    "other",
]:
    names = {a.get("tool") for a in (state.get("actions") or []) if isinstance(a, dict)}
    if state.get("ticket_id") or "handoff_to_human" in names:
        return "handoff"
    if "create_return_request" in names:
        return "return"
    if "book_appointment" in names or "check_availability" in names:
        return "booking"
    if "get_order" in names or "track_shipment" in names:
        return "order_status"
    if "search_knowledge_base" in names:
        return "faq"
    if "upsert_crm_contact" in names:
        return "lead"
    return "other"


def _try_parse_reply(raw: str, state: AgentState) -> AgentReply | None:
    if not raw.strip():
        return None
    candidates = [raw.strip()]
    match = _JSON_RE.search(raw)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and "answer" in data:
                reply = AgentReply.model_validate(data)
                return _enrich(reply, state)
        except (json.JSONDecodeError, ValueError):
            continue
    # Plain text final answer
    if raw.strip() and not raw.strip().startswith("{"):
        return _enrich(
            AgentReply(
                answer=raw.strip(),
                intent=_guess_intent(state),
                actions=_actions_from_state(state),
                citations=list(state.get("citations") or []),
                order_card=state.get("order_card"),
                needs_human=bool(state.get("ticket_id")),
                ticket_id=state.get("ticket_id"),
                confidence=0.7,
            ),
            state,
        )
    return None


def _enrich(reply: AgentReply, state: AgentState) -> AgentReply:
    if not reply.actions:
        reply.actions = _actions_from_state(state)
    if not reply.citations and state.get("citations"):
        reply.citations = [
            c if isinstance(c, Citation) else Citation.model_validate(c)
            for c in (state.get("citations") or [])
        ]
    if reply.order_card is None and state.get("order_card"):
        reply.order_card = state.get("order_card")
    if reply.ticket_id is None and state.get("ticket_id"):
        reply.ticket_id = state.get("ticket_id")
        reply.needs_human = True
    return reply


async def _structured_retry(
    model: BaseChatModel,
    raw: str,
    state: AgentState,
) -> AgentReply | None:
    try:
        structured = model.with_structured_output(AgentReply)
        result = await structured.ainvoke(
            [
                SystemMessage(
                    content="Convert the assistant draft into the AgentReply schema."
                ),
                HumanMessage(content=raw),
            ]
        )
        if isinstance(result, AgentReply):
            return _enrich(result, state)
        if isinstance(result, dict):
            return _enrich(AgentReply.model_validate(result), state)
    except Exception:  # noqa: BLE001 — fall through to text fallback
        return None
    return None

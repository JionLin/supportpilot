"""Structured agent reply schemas (SPEC §6).

@author jiaolin
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Knowledge-base citation shown to the user."""

    document: str
    chunk_id: str
    snippet: str | None = None


class ActionRecord(BaseModel):
    """Record of a tool action taken during the turn."""

    tool: str
    status: Literal["success", "failed", "skipped"]
    summary: str | None = None


class AgentReply(BaseModel):
    """Final structured reply returned by the agent."""

    answer: str
    intent: Literal[
        "faq",
        "order_status",
        "return",
        "booking",
        "lead",
        "handoff",
        "other",
    ]
    actions: list[ActionRecord] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    order_card: dict[str, Any] | None = None
    needs_human: bool = False
    ticket_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)

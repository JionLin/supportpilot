"""Per-invocation tool context (conversation, verified customer, tracer).

@author jiaolin
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.tracing import TraceRecorder


@dataclass
class ToolContext:
    """Shared context passed into tool handlers."""

    conversation_id: str
    tracer: TraceRecorder | None = None
    mock_base_url: str = "http://127.0.0.1:8000"
    verified_customer: dict[str, Any] | None = None
    # Filled by handoff tool for the agent graph.
    handoff_ticket_id: str | None = None
    # Optional DB session for tools that write local tables (handoff/appointments).
    db_session: Any = None
    citations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def conversation_uuid(self) -> UUID | None:
        """Parse conversation_id as UUID when possible.

        Returns:
            UUID | None: Parsed UUID or None.
        """
        try:
            return UUID(self.conversation_id)
        except ValueError:
            return None

"""Trace step recording helpers with PII redaction.

@author jiaolin
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TraceStep

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"\+?\d[\d\-.\s()]{7,}\d")


def redact_pii(value: Any) -> Any:
    """Recursively redact emails and phone numbers from JSON-like data.

    Args:
        value: Arbitrary JSON-serializable structure.

    Returns:
        Any: Structure with emails/phones replaced by placeholders.
    """
    if isinstance(value, str):
        redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", value)
        return _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    if isinstance(value, list):
        return [redact_pii(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_pii(item) for key, item in value.items()}
    return value


class TraceRecorder:
    """Collects tool/agent steps; optionally persists to Postgres."""

    def __init__(
        self,
        *,
        conversation_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Create a recorder.

        Args:
            conversation_id: Optional conversation UUID for persistence.
            run_id: Optional run UUID (generated when missing).
            session: Optional async DB session for persistence.
        """
        self.conversation_id = conversation_id
        self.run_id = run_id or uuid.uuid4()
        self.session = session
        self.steps: list[dict[str, Any]] = []
        self._step_no = 0

    async def record(
        self,
        *,
        node: str,
        tool_name: str | None = None,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        attempt: int = 1,
        latency_ms: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Append a redacted trace step and optionally persist it.

        Args:
            node: Graph node name.
            tool_name: Tool name when node is tools.
            input_data: Tool/LLM input.
            output_data: Tool/LLM output.
            error: Error payload if any.
            attempt: Attempt number (1-based).
            latency_ms: Elapsed milliseconds.
            prompt_tokens: Optional prompt token count.
            completion_tokens: Optional completion token count.

        Returns:
            dict[str, Any]: The recorded step payload.
        """
        self._step_no += 1
        step: dict[str, Any] = {
            "step_no": self._step_no,
            "node": node,
            "tool_name": tool_name,
            "input": redact_pii(input_data),
            "output": redact_pii(output_data),
            "error": redact_pii(error),
            "attempt": attempt,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "run_id": str(self.run_id),
        }
        self.steps.append(step)

        if self.session is not None and self.conversation_id is not None:
            self.session.add(
                TraceStep(
                    conversation_id=self.conversation_id,
                    run_id=self.run_id,
                    step_no=self._step_no,
                    node=node,
                    tool_name=tool_name,
                    input=step["input"],
                    output=step["output"],
                    error=step["error"],
                    attempt=attempt,
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
            )
            await self.session.flush()
        return step

"""Scripted Fake LLM for graph tests (no network).

@author jiaolin
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from typing import Any
from uuid import uuid4

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr


class ScriptedFakeChatModel(BaseChatModel):
    """Returns a predetermined sequence of AIMessages (optionally with tool calls)."""

    script: list[AIMessage] = Field(default_factory=list)
    _index: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted-fake-chat"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ScriptedFakeChatModel:
        """Ignore tools; return self for chaining compatibility.

        Args:
            tools: Tool schemas (ignored).
            **kwargs: Extra bind options (ignored).

        Returns:
            ScriptedFakeChatModel: This instance.
        """
        _ = tools, kwargs
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        _ = messages, stop, run_manager, kwargs
        if self._index >= len(self.script):
            message = AIMessage(
                content=json.dumps(
                    {
                        "answer": "I'm not sure how to help further.",
                        "intent": "other",
                        "actions": [],
                        "citations": [],
                        "order_card": None,
                        "needs_human": False,
                        "ticket_id": None,
                        "confidence": 0.3,
                    }
                )
            )
        else:
            message = self.script[self._index]
            self._index += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


def ai_tool_call(
    name: str,
    args: dict[str, Any],
    *,
    call_id: str | None = None,
) -> AIMessage:
    """Build an AIMessage that requests a single tool call.

    Args:
        name: Tool name.
        args: Tool arguments.
        call_id: Optional tool call id.

    Returns:
        AIMessage: Message with tool_calls.
    """
    tool_call_id = call_id or f"call_{uuid4().hex[:8]}"
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": args,
                "id": tool_call_id,
                "type": "tool_call",
            }
        ],
    )


def ai_text(content: str) -> AIMessage:
    """Build a plain-text AIMessage (final answer).

    Args:
        content: Assistant text.

    Returns:
        AIMessage: Final message without tool calls.
    """
    return AIMessage(content=content)


def iter_script(*messages: AIMessage) -> Iterator[AIMessage]:
    """Yield scripted messages (helper for readability).

    Args:
        *messages: Scripted AI messages.

    Yields:
        AIMessage: Each message in order.
    """
    yield from messages

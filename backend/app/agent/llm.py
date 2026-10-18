"""LLM factory for the support agent.

@author jiaolin
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import Settings, get_settings
from app.tools.schemas import get_openai_tools_schema


def build_chat_model(settings: Settings | None = None) -> ChatOpenAI:
    """Build a ChatOpenAI client pointed at the configured OpenAI-compatible API.

    Args:
        settings: Optional settings override.

    Returns:
        ChatOpenAI: Configured chat model.
    """
    cfg = settings or get_settings()
    return ChatOpenAI(
        model=cfg.llm_model,
        api_key=cfg.llm_api_key or "not-set",
        base_url=cfg.llm_base_url,
        temperature=0,
    )


def bind_tools(model: BaseChatModel) -> Any:
    """Bind SupportPilot tool schemas to a chat model.

    Args:
        model: Base chat model.

    Returns:
        Any: Runnable chat model with tools bound.
    """
    return model.bind_tools(get_openai_tools_schema())

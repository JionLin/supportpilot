"""Outbound webhook helper for handoff / booking events.

@author jiaolin
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential_jitter

from app.config import get_settings

logger = logging.getLogger(__name__)


async def post_webhook(event: str, payload: dict[str, Any]) -> None:
    """POST an event to WEBHOOK_URL with retries; never raise to callers.

    Args:
        event: Event name (e.g. handoff, booking).
        payload: Event payload.
    """
    settings = get_settings()
    url = (settings.webhook_url or "").strip()
    if not url:
        return
    body = {"event": event, "payload": payload}
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=0.5, max=2.0),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(url, json=body)
                    response.raise_for_status()
        logger.info("Webhook %s delivered", event)
    except Exception as exc:  # noqa: BLE001 — must not break main flow
        logger.info("Webhook %s failed after retries: %s", event, exc)

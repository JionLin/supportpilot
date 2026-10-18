"""track_shipment tool adapter.

@author jiaolin
"""

from __future__ import annotations

from typing import Any

import httpx

from app.tools.base import run_tool, tool_result
from app.tools.context import ToolContext
from app.tools.http_client import http_json
from app.tools.schemas import TrackShipmentArgs


async def track_shipment(raw_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Fetch carrier tracking events.

    Args:
        raw_args: Raw LLM tool arguments.
        ctx: Tool invocation context.

    Returns:
        dict[str, Any]: Unified tool result.
    """

    async def _execute(args: TrackShipmentArgs) -> dict[str, Any]:
        url = (
            f"{ctx.mock_base_url.rstrip('/')}/mock/shipping/{args.tracking_number}"
        )
        try:
            data = await http_json(
                "GET",
                url,
                tool_name="track_shipment",
                tracer=ctx.tracer,
                input_for_trace=args.model_dump(mode="json"),
            )
        except httpx.HTTPError as exc:
            return tool_result(
                ok=False,
                code="UPSTREAM_UNAVAILABLE",
                message=str(exc),
                retryable=True,
            )
        return tool_result(ok=True, data=data)

    return await run_tool(
        name="track_shipment",
        args_model=TrackShipmentArgs,
        raw_args=raw_args,
        execute=_execute,
        tracer=ctx.tracer,
        record_execution=False,
    )

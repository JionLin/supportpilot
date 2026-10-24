"""get_order tool adapter.

@author jiaolin
"""

from __future__ import annotations

from typing import Any

import httpx

from app.tools.base import ToolError, run_tool, tool_result
from app.tools.context import ToolContext
from app.tools.http_client import http_json
from app.tools.schemas import GetOrderArgs


async def get_order(raw_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Look up an order via the mock store API.

    Args:
        raw_args: Raw LLM tool arguments.
        ctx: Tool invocation context.

    Returns:
        dict[str, Any]: Unified tool result.
    """

    async def _execute(args: GetOrderArgs) -> dict[str, Any]:
        url = f"{ctx.mock_base_url.rstrip('/')}/mock/orders/{args.order_id}"
        try:
            data = await http_json(
                "GET",
                url,
                tool_name="get_order",
                params={"email": str(args.email)},
                tracer=ctx.tracer,
                input_for_trace=args.model_dump(mode="json"),
            )
        except ToolError as exc:
            if exc.status_code == 404:
                return tool_result(
                    ok=False,
                    code="ORDER_NOT_FOUND",
                    message="Order not found or verification failed",
                    retryable=False,
                )
            raise
        except httpx.HTTPError as exc:
            return tool_result(
                ok=False,
                code="UPSTREAM_UNAVAILABLE",
                message=str(exc),
                retryable=True,
            )
        ctx.verified_customer = {
            "order_id": data.get("order_id"),
            "email": data.get("email"),
            "tracking_number": data.get("tracking_number"),
        }
        return tool_result(ok=True, data=data)

    return await run_tool(
        name="get_order",
        args_model=GetOrderArgs,
        raw_args=raw_args,
        execute=_execute,
        tracer=ctx.tracer,
        record_execution=False,
    )

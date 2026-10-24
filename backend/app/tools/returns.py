"""create_return_request tool adapter.

@author jiaolin
"""

from __future__ import annotations

from typing import Any

import httpx

from app.tools.base import ToolError, idempotency_key, run_tool, tool_result
from app.tools.context import ToolContext
from app.tools.http_client import http_json
from app.tools.schemas import CreateReturnRequestArgs


async def create_return_request(
    raw_args: dict[str, Any], ctx: ToolContext
) -> dict[str, Any]:
    """Create an RMA for a verified order within the return window.

    Args:
        raw_args: Raw LLM tool arguments.
        ctx: Tool invocation context.

    Returns:
        dict[str, Any]: Unified tool result.
    """

    async def _execute(args: CreateReturnRequestArgs) -> dict[str, Any]:
        verified = ctx.verified_customer or {}
        email = verified.get("email")
        if not email or verified.get("order_id") != args.order_id:
            return tool_result(
                ok=False,
                code="VERIFICATION_FAILED",
                message=(
                    "Order must be verified with get_order before creating a return"
                ),
                retryable=False,
            )
        key = idempotency_key(
            ctx.conversation_id,
            {
                "order_id": args.order_id,
                "item_skus": list(args.item_skus),
                "reason": args.reason,
            },
        )
        url = f"{ctx.mock_base_url.rstrip('/')}/mock/returns"
        body = {
            "order_id": args.order_id,
            "email": email,
            "item_skus": list(args.item_skus),
            "reason": args.reason,
            "note": args.note,
            "idempotency_key": key,
        }
        try:
            data = await http_json(
                "POST",
                url,
                tool_name="create_return_request",
                json_body=body,
                tracer=ctx.tracer,
                input_for_trace=body,
            )
        except ToolError as exc:
            return tool_result(
                ok=False,
                code=exc.code,
                message=exc.message,
                retryable=False,
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
        name="create_return_request",
        args_model=CreateReturnRequestArgs,
        raw_args=raw_args,
        execute=_execute,
        tracer=ctx.tracer,
        record_execution=False,
    )

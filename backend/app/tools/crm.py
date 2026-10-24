"""upsert_crm_contact tool adapter.

@author jiaolin
"""

from __future__ import annotations

from typing import Any

import httpx

from app.tools.base import run_tool, tool_result
from app.tools.context import ToolContext
from app.tools.http_client import http_json
from app.tools.schemas import UpsertCrmContactArgs


async def upsert_crm_contact(
    raw_args: dict[str, Any], ctx: ToolContext
) -> dict[str, Any]:
    """Create or update a CRM contact via the mock CRM API.

    Args:
        raw_args: Raw LLM tool arguments.
        ctx: Tool invocation context.

    Returns:
        dict[str, Any]: Unified tool result.
    """

    async def _execute(args: UpsertCrmContactArgs) -> dict[str, Any]:
        url = f"{ctx.mock_base_url.rstrip('/')}/mock/crm/contacts"
        body = args.model_dump(mode="json", exclude_none=True)
        try:
            data = await http_json(
                "PUT",
                url,
                tool_name="upsert_crm_contact",
                json_body=body,
                tracer=ctx.tracer,
                input_for_trace=body,
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
        name="upsert_crm_contact",
        args_model=UpsertCrmContactArgs,
        raw_args=raw_args,
        execute=_execute,
        tracer=ctx.tracer,
        record_execution=False,
    )

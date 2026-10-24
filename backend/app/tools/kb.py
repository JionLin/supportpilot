"""search_knowledge_base tool adapter.

Uses an injectable retriever callable so M4 can wire the real RAG pipeline.

@author jiaolin
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.tools.base import run_tool, tool_result
from app.tools.context import ToolContext
from app.tools.schemas import SearchKnowledgeBaseArgs

RetrieverFn = Callable[[str, int], Awaitable[list[dict[str, Any]]]]

_retriever: RetrieverFn | None = None


def set_knowledge_retriever(retriever: RetrieverFn | None) -> None:
    """Register the RAG retriever used by search_knowledge_base.

    Args:
        retriever: Async callable `(query, top_k) -> hits` or None to clear.
    """
    global _retriever
    _retriever = retriever


async def _default_retriever(query: str, top_k: int) -> list[dict[str, Any]]:
    """Fallback retriever before RAG is wired (returns empty hits).

    Args:
        query: Search query.
        top_k: Max hits.

    Returns:
        list[dict[str, Any]]: Empty list.
    """
    _ = query, top_k
    return []


async def search_knowledge_base(
    raw_args: dict[str, Any], ctx: ToolContext
) -> dict[str, Any]:
    """Search the knowledge base and attach citations to the tool context.

    Args:
        raw_args: Raw LLM tool arguments.
        ctx: Tool invocation context.

    Returns:
        dict[str, Any]: Unified tool result with hits.
    """

    async def _execute(args: SearchKnowledgeBaseArgs) -> dict[str, Any]:
        retriever = _retriever or _default_retriever
        hits = await retriever(args.query, args.top_k)
        citations = [
            {
                "document": hit.get("document", "unknown"),
                "chunk_id": str(hit.get("chunk_id", "")),
                "snippet": hit.get("snippet") or hit.get("content", "")[:240],
            }
            for hit in hits
        ]
        ctx.citations.extend(citations)
        if ctx.tracer is not None:
            await ctx.tracer.record(
                node="tools",
                tool_name="search_knowledge_base",
                input_data=args.model_dump(mode="json"),
                output_data={"hits": hits, "count": len(hits)},
                attempt=1,
            )
        return tool_result(ok=True, data={"hits": hits, "count": len(hits)})

    return await run_tool(
        name="search_knowledge_base",
        args_model=SearchKnowledgeBaseArgs,
        raw_args=raw_args,
        execute=_execute,
        tracer=ctx.tracer,
        record_execution=False,
    )

"""pgvector cosine similarity retriever.

@author jiaolin
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import KbChunk, KbDocument
from app.rag.embedder import Embedder, build_embedder


@dataclass(frozen=True)
class RetrievalHit:
    """A single retrieval result."""

    chunk_id: UUID
    document_id: UUID
    document: str
    content: str
    snippet: str
    distance: float
    metadata: dict[str, Any] | None


class KnowledgeRetriever:
    """Retrieve KB chunks by cosine distance against an embedded query."""

    def __init__(
        self,
        session: AsyncSession,
        embedder: Embedder | None = None,
        *,
        distance_threshold: float | None = None,
    ) -> None:
        """Create a retriever.

        Args:
            session: Async DB session.
            embedder: Optional embedder override.
            distance_threshold: Max cosine distance (default from settings/0.35).
        """
        self.session = session
        self.embedder = embedder or build_embedder()
        settings = get_settings()
        self.distance_threshold = (
            distance_threshold
            if distance_threshold is not None
            else float(getattr(settings, "rag_distance_threshold", 0.35))
        )

    async def search(self, query: str, top_k: int = 4) -> list[RetrievalHit]:
        """Search ready knowledge chunks.

        Args:
            query: Natural language query.
            top_k: Maximum hits to return.

        Returns:
            list[RetrievalHit]: Hits sorted by ascending distance.
        """
        if not query.strip():
            return []
        vector = await self.embedder.embed_query(query)
        # pgvector cosine distance operator: <=>
        distance_expr = KbChunk.embedding.cosine_distance(vector)
        statement = (
            select(
                KbChunk,
                KbDocument,
                distance_expr.label("distance"),
            )
            .join(KbDocument, KbDocument.id == KbChunk.document_id)
            .where(KbDocument.status == "ready")
            .where(KbChunk.embedding.is_not(None))
            .where(distance_expr <= self.distance_threshold)
            .order_by(distance_expr)
            .limit(top_k)
        )
        result = await self.session.execute(statement)
        hits: list[RetrievalHit] = []
        for chunk, document, distance in result.all():
            content = chunk.content
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document=document.title or document.source_uri or str(document.id),
                    content=content,
                    snippet=content[:240],
                    distance=float(distance),
                    metadata=chunk.chunk_metadata,
                )
            )
        return hits


def hits_as_dicts(hits: list[RetrievalHit]) -> list[dict[str, Any]]:
    """Convert retrieval hits to JSON-friendly dicts for tools/API.

    Args:
        hits: Retrieval hits.

    Returns:
        list[dict[str, Any]]: Serialized hits.
    """
    return [
        {
            "chunk_id": str(hit.chunk_id),
            "document_id": str(hit.document_id),
            "document": hit.document,
            "content": hit.content,
            "snippet": hit.snippet,
            "distance": hit.distance,
            "metadata": hit.metadata,
        }
        for hit in hits
    ]

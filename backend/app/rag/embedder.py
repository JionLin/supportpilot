"""OpenAI-compatible embedding client with fake mode for tests.

@author jiaolin
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Protocol

from openai import AsyncOpenAI
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    """Embedding provider protocol."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple documents.

        Args:
            texts: Input strings.

        Returns:
            list[list[float]]: Embedding vectors.
        """

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string.

        Args:
            text: Query text.

        Returns:
            list[float]: Embedding vector.
        """


class FakeEmbedder:
    """Deterministic hash-based embedder for offline tests."""

    def __init__(self, dim: int = 1536) -> None:
        """Create a fake embedder.

        Args:
            dim: Embedding dimensionality.
        """
        self.dim = dim

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents deterministically.

        Args:
            texts: Input strings.

        Returns:
            list[list[float]]: Unit vectors derived from text hashes.
        """
        return [self._vector(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        """Embed a query deterministically.

        Args:
            text: Query text.

        Returns:
            list[float]: Unit vector.
        """
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        while len(values) < self.dim:
            for byte in digest:
                values.append((byte / 255.0) * 2.0 - 1.0)
                if len(values) >= self.dim:
                    break
            digest = hashlib.sha256(digest).digest()
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


class OpenAICompatEmbedder:
    """Embedding client pointing at an OpenAI-compatible API."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Create the client from settings.

        Args:
            settings: Optional settings override.
        """
        self.settings = settings or get_settings()
        self._client = AsyncOpenAI(
            api_key=self.settings.resolved_embedding_api_key or "not-set",
            base_url=self.settings.resolved_embedding_base_url,
        )
        self.model = self.settings.embedding_model
        self.dim = self.settings.embedding_dim

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Batch-embed documents with retry.

        Args:
            texts: Input strings.

        Returns:
            list[list[float]]: Embedding vectors.
        """
        if not texts:
            return []
        return await self._embed(texts)

    async def embed_query(self, text: str) -> list[float]:
        """Embed a query with retry.

        Args:
            text: Query text.

        Returns:
            list[float]: Embedding vector.
        """
        vectors = await self._embed([text])
        return vectors[0]

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=0.5, max=2.0),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                response = await self._client.embeddings.create(
                    model=self.model,
                    input=texts,
                )
                vectors = [list(item.embedding) for item in response.data]
                for vector in vectors:
                    if len(vector) != self.dim:
                        logger.info(
                            "Embedding dim mismatch: got %s expected %s",
                            len(vector),
                            self.dim,
                        )
                return vectors
        msg = "embed exhausted without result"
        raise RuntimeError(msg)


def build_embedder(*, fake: bool | None = None) -> Embedder:
    """Build an embedder; use fake when no API key is configured.

    Args:
        fake: Force fake embedder when True.

    Returns:
        Embedder: Configured embedder instance.
    """
    settings = get_settings()
    use_fake = (
        fake
        if fake is not None
        else not bool(settings.resolved_embedding_api_key)
    )
    if use_fake:
        return FakeEmbedder(dim=settings.embedding_dim)
    return OpenAICompatEmbedder(settings)

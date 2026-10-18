"""Tests for RAG splitter, ingest, and retrieval (fake embeddings).

@author jiaolin
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from scripts.seed import KB_DOCUMENT_IDS, seed_all
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import KbChunk
from app.db.session import reset_engine
from app.main import create_app
from app.rag.embedder import FakeEmbedder
from app.rag.retriever import KnowledgeRetriever
from app.rag.service import (
    create_document_from_upload,
    delete_document,
    process_document,
)
from app.rag.splitter import split_text


def test_split_text_respects_size_and_overlap() -> None:
    """Splitter produces overlapping chunks under the size limit."""
    text = "# Title\n\n" + ("word " * 400)
    chunks = split_text(text, chunk_size=800, chunk_overlap=120)
    assert len(chunks) >= 2
    assert all(len(chunk.content) <= 800 + len("# Title\n\n") for chunk in chunks)
    assert chunks[0].heading == "# Title"


@pytest.mark.asyncio
async def test_process_seed_document_and_search(db_session: AsyncSession) -> None:
    """Seed markdown is embedded with FakeEmbedder and searchable."""
    await seed_all(db_session)
    document_id = KB_DOCUMENT_IDS["return-policy.md"]
    embedder = FakeEmbedder(dim=1536)
    document = await process_document(db_session, document_id, embedder=embedder)
    assert document.status == "ready"
    assert (document.chunk_count or 0) >= 1

    chunks = (
        await db_session.execute(
            select(KbChunk).where(KbChunk.document_id == document_id)
        )
    ).scalars().all()
    assert len(chunks) >= 1
    assert chunks[0].embedding is not None

    retriever = KnowledgeRetriever(
        db_session,
        embedder=embedder,
        distance_threshold=1.5,
    )
    probe = chunks[0].content[:120]
    hits = await retriever.search(probe, top_k=3)
    assert len(hits) >= 1
    assert str(hits[0].chunk_id) == str(chunks[0].id)


@pytest.mark.asyncio
async def test_kb_api_list_and_search(db_session: AsyncSession) -> None:
    """KB list and search endpoints work after seed ingest."""
    await seed_all(db_session)
    get_settings.cache_clear()
    reset_engine()
    application = create_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await client.get("/api/kb/documents")
        assert listed.status_code == 200
        docs = listed.json()["documents"]
        assert len(docs) >= 5

        search = await client.post(
            "/api/kb/search",
            json={"query": "shipping rates", "top_k": 3},
        )
        assert search.status_code == 200
        assert "hits" in search.json()


@pytest.mark.asyncio
async def test_kb_upload_and_delete(db_session: AsyncSession) -> None:
    """TXT upload creates a document that processes and can be deleted."""
    content = b"# Demo\n\nReturn within 30 days for a full refund."
    document = await create_document_from_upload(
        db_session,
        title="Demo Doc",
        source_type="txt",
        filename="demo.txt",
        content=content,
    )
    assert document.status == "pending"
    document_id = document.id
    processed = await process_document(
        db_session, document_id, embedder=FakeEmbedder(dim=1536)
    )
    assert processed.status == "ready"
    assert (processed.chunk_count or 0) >= 1

    deleted = await delete_document(db_session, document_id)
    assert deleted is True
    remaining = await db_session.execute(
        select(KbChunk).where(KbChunk.document_id == document_id)
    )
    assert remaining.scalars().first() is None

"""Knowledge-base ingest pipeline (load → split → embed → store).

@author jiaolin
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KbChunk, KbDocument
from app.rag.embedder import Embedder, build_embedder
from app.rag.loader import load_text_from_path, load_text_from_url
from app.rag.splitter import split_text

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


async def process_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    *,
    embedder: Embedder | None = None,
) -> KbDocument:
    """Process a pending KB document into embedded chunks.

    Args:
        session: Async DB session.
        document_id: Document primary key.
        embedder: Optional embedder override.

    Returns:
        KbDocument: Updated document row.
    """
    result = await session.execute(
        select(KbDocument).where(KbDocument.id == document_id)
    )
    document = result.scalar_one()
    document.status = "processing"
    document.error = None
    await session.commit()

    try:
        text = await _load_document_text(document)
        chunks = split_text(text)
        active_embedder = embedder or build_embedder()
        vectors = await active_embedder.embed_documents([c.content for c in chunks])

        await session.execute(
            delete(KbChunk).where(KbChunk.document_id == document.id)
        )
        for chunk, vector in zip(chunks, vectors, strict=True):
            session.add(
                KbChunk(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    chunk_metadata={"heading": chunk.heading},
                    embedding=vector,
                )
            )
        document.status = "ready"
        document.chunk_count = len(chunks)
        document.error = None
        await session.commit()
        logger.info(
            "KB document %s ready with %s chunks",
            document.id,
            document.chunk_count,
        )
        return document
    except Exception as exc:  # noqa: BLE001 — persist failure status
        await session.rollback()
        result = await session.execute(
            select(KbDocument).where(KbDocument.id == document_id)
        )
        document = result.scalar_one()
        document.status = "failed"
        document.error = str(exc)
        await session.commit()
        logger.info("KB document %s failed: %s", document_id, exc)
        return document


async def _load_document_text(document: KbDocument) -> str:
    source_type = document.source_type or "txt"
    source_uri = document.source_uri or ""
    if source_type == "url":
        return await load_text_from_url(source_uri)
    path = Path(source_uri)
    return await load_text_from_path(path, source_type)


async def create_document_from_upload(
    session: AsyncSession,
    *,
    title: str,
    source_type: str,
    filename: str,
    content: bytes,
) -> KbDocument:
    """Persist an uploaded file and create a pending KB document row.

    Args:
        session: Async DB session.
        title: Document title.
        source_type: pdf/md/txt.
        filename: Original filename.
        content: Raw bytes.

    Returns:
        KbDocument: Created pending document.
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    document_id = uuid.uuid4()
    suffix = Path(filename).suffix or f".{source_type}"
    path = UPLOAD_DIR / f"{document_id}{suffix}"
    path.write_bytes(content)
    document = KbDocument(
        id=document_id,
        title=title or Path(filename).stem,
        source_type=source_type,
        source_uri=str(path),
        status="pending",
        chunk_count=0,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def create_document_from_url(
    session: AsyncSession,
    *,
    url: str,
    title: str | None = None,
) -> KbDocument:
    """Create a pending KB document from a URL.

    Args:
        session: Async DB session.
        url: Source URL.
        title: Optional title override.

    Returns:
        KbDocument: Created pending document.
    """
    document = KbDocument(
        id=uuid.uuid4(),
        title=title or url,
        source_type="url",
        source_uri=url,
        status="pending",
        chunk_count=0,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def delete_document(session: AsyncSession, document_id: uuid.UUID) -> bool:
    """Delete a document and its chunks (and local upload file if present).

    Args:
        session: Async DB session.
        document_id: Document id.

    Returns:
        bool: True when a row was deleted.
    """
    result = await session.execute(
        select(KbDocument).where(KbDocument.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        return False
    if document.source_type != "url" and document.source_uri:
        path = Path(document.source_uri)
        if path.is_file() and UPLOAD_DIR in path.parents:
            path.unlink(missing_ok=True)
    await session.execute(delete(KbChunk).where(KbChunk.document_id == document_id))
    await session.delete(document)
    await session.commit()
    return True


async def list_documents(session: AsyncSession) -> list[dict[str, Any]]:
    """List KB documents with status metadata.

    Args:
        session: Async DB session.

    Returns:
        list[dict[str, Any]]: Document summaries.
    """
    result = await session.execute(
        select(KbDocument).order_by(KbDocument.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "source_type": row.source_type,
            "source_uri": row.source_uri,
            "status": row.status,
            "chunk_count": row.chunk_count,
            "error": row.error,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


async def ingest_seed_kb(
    session: AsyncSession,
    *,
    embedder: Embedder | None = None,
) -> int:
    """Process all seed_kb documents that are not yet ready.

    Args:
        session: Async DB session.
        embedder: Optional embedder override.

    Returns:
        int: Number of documents processed.
    """
    result = await session.execute(
        select(KbDocument).where(
            KbDocument.source_type == "md",
            KbDocument.status.in_(["pending", "failed"]),
        )
    )
    documents = result.scalars().all()
    count = 0
    for document in documents:
        await process_document(session, document.id, embedder=embedder)
        count += 1
    return count

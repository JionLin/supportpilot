"""Knowledge-base HTTP API.

@author jiaolin
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session, get_session_factory
from app.rag.embedder import build_embedder
from app.rag.retriever import KnowledgeRetriever, hits_as_dicts
from app.rag.service import (
    create_document_from_upload,
    create_document_from_url,
    delete_document,
    list_documents,
    process_document,
)

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])

_SOURCE_BY_SUFFIX = {
    ".pdf": "pdf",
    ".md": "md",
    ".markdown": "md",
    ".txt": "txt",
}


class UrlIngestRequest(BaseModel):
    """JSON body for URL ingest."""

    url: HttpUrl
    title: str | None = None


class SearchRequest(BaseModel):
    """Debug search request."""

    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=8)


async def _process_in_background(document_id: uuid.UUID) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await process_document(session, document_id, embedder=build_embedder())


@router.get("/documents")
async def get_documents(
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """List knowledge-base documents.

    Args:
        session: DB session.

    Returns:
        dict[str, Any]: Documents list.
    """
    return {"documents": await list_documents(session)}


@router.post("/documents", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    title: str | None = Form(default=None),
) -> dict[str, Any]:
    """Upload a file or accept a URL form field for ingest.

    Args:
        background_tasks: FastAPI background task queue.
        session: DB session.
        file: Optional uploaded file.
        url: Optional URL form field.
        title: Optional title.

    Returns:
        dict[str, Any]: Accepted document metadata.
    """
    if file is not None and file.filename:
        suffix = Path(file.filename).suffix.lower()
        source_type = _SOURCE_BY_SUFFIX.get(suffix)
        if source_type is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "UNSUPPORTED_TYPE",
                    "message": "Only pdf/md/txt uploads are supported",
                },
            )
        content = await file.read()
        document = await create_document_from_upload(
            session,
            title=title or Path(file.filename).stem,
            source_type=source_type,
            filename=file.filename,
            content=content,
        )
    elif url:
        document = await create_document_from_url(session, url=url, title=title)
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "MISSING_SOURCE",
                "message": "Provide a file upload or url form field",
            },
        )

    background_tasks.add_task(_process_in_background, document.id)
    return {
        "id": str(document.id),
        "title": document.title,
        "status": document.status,
        "source_type": document.source_type,
    }


@router.post("/documents/url", status_code=202)
async def ingest_url(
    body: UrlIngestRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Ingest a document from a JSON URL payload.

    Args:
        body: URL ingest request.
        background_tasks: Background task queue.
        session: DB session.

    Returns:
        dict[str, Any]: Accepted document metadata.
    """
    document = await create_document_from_url(
        session,
        url=str(body.url),
        title=body.title,
    )
    background_tasks.add_task(_process_in_background, document.id)
    return {
        "id": str(document.id),
        "title": document.title,
        "status": document.status,
        "source_type": document.source_type,
    }


@router.delete("/documents/{document_id}", status_code=204)
async def remove_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete a document and its vectors.

    Args:
        document_id: Document UUID.
        session: DB session.
    """
    deleted = await delete_document(session, document_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Document not found"},
        )


@router.post("/search")
async def search_kb(
    body: SearchRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Debug retrieval endpoint.

    Args:
        body: Search request.
        session: DB session.

    Returns:
        dict[str, Any]: Hits list.
    """
    retriever = KnowledgeRetriever(session, embedder=build_embedder())
    hits = await retriever.search(body.query, top_k=body.top_k)
    return {"hits": hits_as_dicts(hits)}

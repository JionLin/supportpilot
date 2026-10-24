"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.appointments import router as appointments_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.kb import router as kb_router
from app.api.tickets import router as tickets_router
from app.config import get_settings
from app.db.session import get_session_factory
from app.mock_services import router as mock_router
from app.mock_services.runtime import reset_mock_runtime
from app.rag.embedder import build_embedder
from app.rag.retriever import KnowledgeRetriever, hits_as_dicts
from app.rag.service import ingest_seed_kb
from app.tools.kb import set_knowledge_retriever


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """Initialize runtime mock chaos settings and wire KB retriever.

    Args:
        _application: FastAPI app instance.

    Yields:
        None: Application lifespan.
    """
    settings = get_settings()
    reset_mock_runtime(
        latency_ms=settings.mock_latency_ms,
        failure_rate=settings.mock_failure_rate,
    )

    async def _retriever(query: str, top_k: int) -> list[dict[str, object]]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            use_fake: bool | None = True if settings.use_fake_embeddings else None
            retriever = KnowledgeRetriever(
                session,
                embedder=build_embedder(fake=use_fake),
            )
            hits = await retriever.search(query, top_k=top_k)
            return hits_as_dicts(hits)

    set_knowledge_retriever(_retriever)

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            await ingest_seed_kb(
                session,
                embedder=build_embedder(
                    fake=settings.use_fake_embeddings
                    or not bool(settings.resolved_embedding_api_key)
                ),
            )
    except Exception:  # noqa: BLE001 — startup should not crash without DB
        pass

    yield
    set_knowledge_retriever(None)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance.
    """
    settings = get_settings()
    application = FastAPI(
        title="SupportPilot",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(mock_router)
    application.include_router(kb_router)
    application.include_router(chat_router)
    application.include_router(conversations_router)
    application.include_router(tickets_router)
    application.include_router(appointments_router)
    application.include_router(admin_router)
    return application


app = create_app()

"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import get_settings
from app.mock_services import router as mock_router
from app.mock_services.runtime import reset_mock_runtime


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """Initialize runtime mock chaos settings from environment.

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
    yield


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
    application.include_router(health_router)
    application.include_router(mock_router)
    return application


app = create_app()

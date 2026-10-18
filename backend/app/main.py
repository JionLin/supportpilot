"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import get_settings


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance.
    """
    settings = get_settings()
    application = FastAPI(title="SupportPilot", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    return application


app = create_app()

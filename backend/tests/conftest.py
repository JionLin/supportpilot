"""Shared pytest fixtures for database integration tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.session import reset_engine


def _host_database_url() -> str:
    """Prefer DATABASE_URL, rewriting Docker hostname for host-side tests."""
    settings = get_settings()
    url = os.environ.get("DATABASE_URL", settings.database_url)
    return url.replace("@db:", "@127.0.0.1:")


@pytest.fixture(scope="session")
def database_url() -> str:
    """Return the async database URL used by tests.

    Returns:
        str: Async SQLAlchemy URL pointing at compose Postgres.
    """
    return _host_database_url()


@pytest.fixture(scope="session", autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """Clear cached settings so env overrides are visible.

    Yields:
        None: Fixture lifespan marker.
    """
    get_settings.cache_clear()
    reset_engine()
    yield
    get_settings.cache_clear()
    reset_engine()


@pytest_asyncio.fixture
async def db_session(database_url: str) -> AsyncIterator[AsyncSession]:
    """Yield an async session bound to the compose database.

    Args:
        database_url: Async database URL.

    Yields:
        AsyncSession: Open async session.
    """
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        # Fail fast if Postgres is unreachable.
        await session.execute(text("SELECT 1"))
        yield session
    await engine.dispose()

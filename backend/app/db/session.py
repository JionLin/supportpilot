"""Async SQLAlchemy engine and session helpers."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return a process-wide async engine.

    Returns:
        AsyncEngine: Shared async SQLAlchemy engine.
    """
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared async session factory.

    Returns:
        async_sessionmaker[AsyncSession]: Session factory bound to the engine.
    """
    get_engine()
    assert _session_factory is not None
    return _session_factory


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session.

    Yields:
        AsyncSession: A request-scoped async session.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


def reset_engine() -> None:
    """Clear the cached engine and session factory (for tests)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None

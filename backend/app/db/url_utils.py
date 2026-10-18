"""Helpers for database URL conversion."""


def to_sync_database_url(async_url: str) -> str:
    """Convert an async SQLAlchemy URL to a sync psycopg URL.

    Args:
        async_url: Async database URL (typically postgresql+asyncpg://...).

    Returns:
        str: Sync URL suitable for Alembic (postgresql+psycopg://...).
    """
    if async_url.startswith("postgresql+asyncpg://"):
        return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if async_url.startswith("postgres://"):
        return async_url.replace("postgres://", "postgresql+psycopg://", 1)
    if async_url.startswith("postgresql://"):
        return async_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return async_url

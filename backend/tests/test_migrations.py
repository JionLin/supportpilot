"""Tests for Alembic migrations against compose Postgres."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _run_migrations(database_url: str) -> None:
    """Apply Alembic migrations to head.

    Args:
        database_url: Async database URL used by the application settings.
    """
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "app/db/migrations"))
    config.set_main_option("path_separator", "os")
    command.upgrade(config, "head")


async def test_schema_objects_exist(
    db_session: AsyncSession, database_url: str
) -> None:
    """After migrations, required tables, extension, and HNSW index exist."""
    _run_migrations(database_url)

    extension = await db_session.scalar(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    )
    assert extension == "vector"

    tables = {
        row[0]
        for row in (
            await db_session.execute(
                text(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    """
                )
            )
        ).all()
    }
    expected = {
        "conversations",
        "messages",
        "trace_steps",
        "kb_documents",
        "kb_chunks",
        "tickets",
        "appointments",
        "mock_orders",
        "mock_shipments",
        "mock_slots",
        "mock_crm_contacts",
        "mock_returns",
        "alembic_version",
    }
    assert expected.issubset(tables)

    index_names = {
        row[0]
        for row in (
            await db_session.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'kb_chunks'
                    """
                )
            )
        ).all()
    }
    assert "ix_kb_chunks_embedding_hnsw" in index_names

    dim = await db_session.scalar(
        text(
            """
            SELECT (SELECT format_type(a.atttypid, a.atttypmod))
            FROM pg_attribute a
            WHERE a.attrelid = 'kb_chunks'::regclass
              AND a.attname = 'embedding'
              AND a.attnum > 0
              AND NOT a.attisdropped
            """
        )
    )
    expected_dim = int(os.environ.get("EMBEDDING_DIM", "1536"))
    assert dim == f"vector({expected_dim})"

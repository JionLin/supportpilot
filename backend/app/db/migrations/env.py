"""Alembic environment configuration (sync psycopg for CLI and tests)."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db import models as _models  # noqa: F401
from app.db.base import Base
from app.db.url_utils import to_sync_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    return to_sync_database_url(get_settings().database_url)


def _embedding_dim() -> int:
    raw = os.environ.get("EMBEDDING_DIM")
    if raw is not None and raw.strip():
        return int(raw)
    return get_settings().embedding_dim


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode with a sync engine."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        connection.info["embedding_dim"] = _embedding_dim()
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

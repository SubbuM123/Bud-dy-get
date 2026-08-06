"""Alembic migration environment configuration.

This module is executed by every `alembic` CLI invocation (revision,
upgrade, downgrade). It points Alembic at the app's async SQLAlchemy engine
and at `Base.metadata` so that `alembic revision --autogenerate` can diff the
live database against the ORM models in app/models and generate a migration
script automatically. The `from app.models import *` import is required so
every model class is registered on Base.metadata before that diff runs.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import get_settings
from app.database import Base
from app.models import *

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


# Emit SQL to stdout instead of executing it against a live database (`alembic upgrade --sql`).
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# Run pending migrations against the given synchronous-style connection.
def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


# Open an async engine and run migrations through it via run_sync (Alembic itself is sync).
async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# Entry point for normal `alembic upgrade`/`alembic downgrade` invocations.
def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

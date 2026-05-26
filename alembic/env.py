from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, async_engine_from_config

import app.db.models  # noqa: F401  (register SQLAlchemy models on Base.metadata)
from alembic import context
from app.core.database import Base

# this is the Alembic Config object, which provides access to the values
# within the .ini file in use.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _pick_database_url() -> str | None:
    # Prefer runtime DATABASE_URL (app); fall back to DATABASE_URL_TEST (tests).
    return os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_TEST")


if (database_url := _pick_database_url()) is not None:
    config.set_main_option("sqlalchemy.url", database_url)


# target_metadata is used for 'autogenerate' support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("Missing sqlalchemy.url in Alembic config")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        pool_pre_ping=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())

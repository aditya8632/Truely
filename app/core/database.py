from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


engine: AsyncEngine = make_engine(settings.database_url)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def wait_for_postgres_ready(database_url: str, timeout_seconds: int = 30) -> None:
    eng = make_engine(database_url)
    deadline = datetime.now(UTC).timestamp() + timeout_seconds
    last_err: Exception | None = None

    while datetime.now(UTC).timestamp() < deadline:
        try:
            async with eng.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
                return
        except Exception as exc:  # pragma: no cover
            last_err = exc
            await asyncio.sleep(1.5)

    if last_err is not None:  # pragma: no cover
        raise RuntimeError(f"Database not ready: {last_err}") from last_err
    raise RuntimeError("Database not ready")

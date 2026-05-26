from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

import asyncpg
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _normalize_postgres_host(url: str) -> str:
    # Common docker-compose hostname: `postgres`. When tests run on the host,
    # `postgres` usually does not resolve.
    return url.replace("@postgres:", "@localhost:")


def _parse_pg_admin_params(url: str) -> tuple[str, str, str, int, str]:
    # Returns (user, password, host, port, database)
    # Expected format: postgresql+asyncpg://user:pass@host:port/dbname
    # We'll do a simple split to avoid adding extra deps.
    without_scheme = url.split("://", 1)[1]
    user_pass, rest = without_scheme.split("@", 1)
    user, password = user_pass.split(":", 1)
    host_port, database = rest.split("/", 1)
    host, port_str = host_port.split(":", 1)
    return user, password, host, int(port_str), database


async def _wait_for_postgres(url: str, timeout_seconds: int = 90) -> None:
    user, password, host, port, _db = _parse_pg_admin_params(url)

    deadline = time.time() + timeout_seconds
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            await asyncpg.connect(
                user=user, password=password, host=host, port=port, database="postgres"
            ).close()
            return
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            await asyncio_sleep(1.2)

    raise RuntimeError(f"Postgres not reachable: {last_exc}")  # pragma: no cover


async def asyncio_sleep(seconds: float) -> None:
    # Local helper to avoid importing asyncio at module import time.
    import asyncio

    await asyncio.sleep(seconds)


def _ensure_test_database_exists(url: str) -> None:
    async def _inner() -> None:
        user, password, host, port, db = _parse_pg_admin_params(url)
        conn = await asyncpg.connect(
            user=user, password=password, host=host, port=port, database="postgres"
        )
        try:
            try:
                await conn.execute(f'CREATE DATABASE "{db}"')
            except asyncpg.exceptions.DuplicateDatabaseError:
                pass
        finally:
            await conn.close()

    import asyncio

    asyncio.run(_inner())


def _run_migrations(database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["DATABASE_URL_TEST"] = database_url

    cmd = [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"]
    subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT), env=env)


@pytest.fixture(scope="session")
def integration_db_bootstrap() -> Iterator[None]:
    test_url = os.getenv(
        "DATABASE_URL_TEST", "postgresql+asyncpg://postgres:postgres@localhost:5432/grants_svc_test"
    )
    test_url = _normalize_postgres_host(test_url)

    # Make the app pick up the test database during import.
    os.environ["DATABASE_URL"] = test_url
    os.environ["DATABASE_URL_TEST"] = test_url

    # Start docker-compose only if Postgres is unreachable.
    # (Useful when running tests locally without already starting the stack.)
    import asyncio

    async def _try_connect() -> bool:
        user, password, host, port, _db = _parse_pg_admin_params(test_url)
        try:
            conn = await asyncpg.connect(
                user=user, password=password, host=host, port=port, database="postgres"
            )
            await conn.close()
            return True
        except Exception:
            return False

    connected = asyncio.run(_try_connect())
    if not connected:
        # Best-effort: start the stack.
        try:
            subprocess.run(
                ["docker", "compose", "up", "-d", "--build"],
                check=False,
                cwd=str(PROJECT_ROOT),
            )
        except FileNotFoundError:
            pytest.skip(
                "Postgres unreachable and docker is not available; skipping integration tests."
            )

        asyncio.run(_wait_for_postgres(test_url))

    _ensure_test_database_exists(test_url)
    _run_migrations(test_url)

    yield


@pytest.fixture(scope="session")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture()
async def app() -> AsyncGenerator[object, None]:
    # Import after environment variables are set.
    from app.main import app as fastapi_app

    yield fastapi_app


@pytest.fixture()
async def client(
    integration_db_bootstrap,
    app,
    db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncClient, None]:
    # Keep users/documents seeded; remove grants between tests for isolation.
    async with db_engine.begin() as conn:
        await conn.execute("TRUNCATE TABLE grants_svc.grants RESTART IDENTITY CASCADE;")

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

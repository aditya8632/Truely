from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

# Deterministic UUIDs for repeatable tests and dev environments.
SEED_USERS: dict[str, str] = {
    "Alice": "11111111-1111-1111-1111-111111111111",
    "Bob": "22222222-2222-2222-2222-222222222222",
    "Carol": "33333333-3333-3333-3333-333333333333",
}

SEED_DOCUMENTS: dict[str, str] = {
    "Q1 Report": "44444444-4444-4444-4444-444444444444",
    "Product Roadmap": "55555555-5555-5555-5555-555555555555",
    "Budget 2026": "66666666-6666-6666-6666-666666666666",
}


async def seed_users_and_documents(session: AsyncSession) -> None:
    # Idempotent seed; Alembic migration already seeds, but this keeps local dev consistent.
    users_sql = f"""
    INSERT INTO {settings.schema_name}.users (id, name)
    VALUES
    ('{SEED_USERS["Alice"]}', 'Alice'),
    ('{SEED_USERS["Bob"]}', 'Bob'),
    ('{SEED_USERS["Carol"]}', 'Carol')
    ON CONFLICT (id) DO NOTHING;
    """
    docs_sql = f"""
    INSERT INTO {settings.schema_name}.documents (id, title)
    VALUES
    ('{SEED_DOCUMENTS["Q1 Report"]}', 'Q1 Report'),
    ('{SEED_DOCUMENTS["Product Roadmap"]}', 'Product Roadmap'),
    ('{SEED_DOCUMENTS["Budget 2026"]}', 'Budget 2026')
    ON CONFLICT (id) DO NOTHING;
    """

    await session.execute(sa.text(users_sql))
    await session.execute(sa.text(docs_sql))

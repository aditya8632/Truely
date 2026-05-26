from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.grants import router as grants_router
from app.core.config import settings
from app.core.database import session_scope, wait_for_postgres_ready
from app.db.seed import seed_users_and_documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    await wait_for_postgres_ready(settings.database_url, timeout_seconds=60)
    # Keep dev/test environments consistent even if migrations weren't run yet.
    async with session_scope() as session:
        await seed_users_and_documents(session)
        await session.commit()
    yield


app = FastAPI(title="Document Access Grants Service", lifespan=lifespan)
app.include_router(grants_router)


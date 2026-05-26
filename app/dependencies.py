from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import session_scope
from app.services.grants import GrantService


def _parse_iso_datetime(value: str) -> datetime:
    # Support common `Z` suffix.
    v = value.replace("Z", "+00:00") if value.endswith("Z") else value
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None or dt.utcoffset() is None:
        # Treat naive timestamps as UTC for convenience.
        return dt.replace(tzinfo=UTC)
    return dt


async def get_db_session() -> AsyncSession:
    async with session_scope() as session:
        yield session


def get_now_header(x_now: str | None = Header(default=None, alias=settings.now_header)) -> datetime:
    if x_now is None:
        return datetime.now(UTC)
    try:
        return _parse_iso_datetime(x_now)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-Now datetime") from exc


def get_now_provider(now: datetime = Depends(get_now_header)) -> Callable[[], datetime]:
    # Capture `now` so the service is consistent across all operations in one request.
    return lambda: now


def get_current_user_id(
    x_user_id: str | None = Header(default=None, alias=settings.current_user_header),
) -> UUID:
    if x_user_id is None:
        raise HTTPException(
            status_code=400,
            detail=f"Missing {settings.current_user_header} header",
        )
    try:
        return UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id UUID") from exc


async def get_grant_service(
    session: AsyncSession = Depends(get_db_session),
    now_provider: Callable[[], datetime] = Depends(get_now_provider),
) -> GrantService:
    return GrantService(session=session, now_provider=now_provider)

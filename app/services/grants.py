from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.grants import GrantsRepository
from app.schemas.grant import GrantCreate


class GrantService:
    def __init__(self, *, session: AsyncSession, now_provider):
        self.session = session
        self.repo = GrantsRepository(session)
        self.now_provider = now_provider

    def _now(self) -> datetime:
        now = self.now_provider()
        if now.tzinfo is None or now.utcoffset() is None:
            raise RuntimeError("now_provider must return a timezone-aware datetime")
        return now

    async def create_grant(self, *, data: GrantCreate, current_user_id: UUID):
        now = self._now()
        if data.expires_at < now + timedelta(minutes=1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="expires_at must be at least 1 minute in the future",
            )

        async with self.session.begin():
            # Internal housekeeping: make partial unique index usable by ensuring any expired
            # grants for the pair are marked revoked before inserting the new one.
            await self.repo.cleanup_expired_unrevoked_for_pair(
                granted_to_user_id=data.granted_to_user_id,
                document_id=data.document_id,
                now=now,
            )

            existing = await self.repo.get_active_grant_for_pair(
                granted_to_user_id=data.granted_to_user_id,
                document_id=data.document_id,
                now=now,
            )
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only one active grant is allowed per (granted_to_user_id, document_id)",
                )

            try:
                grant = await self.repo.create_grant(
                    document_id=data.document_id,
                    granted_to_user_id=data.granted_to_user_id,
                    granted_by_user_id=current_user_id,
                    permission=data.permission,
                    expires_at=data.expires_at,
                    created_at=now,
                )
            except IntegrityError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Grant already exists for this pair",
                ) from exc

            return grant

    async def list_grants(
        self,
        *,
        document_id: UUID | None,
        granted_to_user_id: UUID | None,
        active_only: bool,
        limit: int,
        offset: int,
    ):
        now = self._now()
        items, total = await self.repo.list_grants(
            document_id=document_id,
            granted_to_user_id=granted_to_user_id,
            active_only=active_only,
            now=now,
            limit=limit,
            offset=offset,
        )
        return items, total

    async def get_grant(self, *, grant_id: UUID):
        grant = await self.repo.get_grant_by_id(grant_id=grant_id)
        if grant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")
        return grant

    async def check_active(self, *, grant_id: UUID):
        now = self._now()
        grant = await self.get_grant(grant_id=grant_id)
        return bool(grant.revoked_at is None and grant.expires_at > now)

    async def revoke_grant(self, *, grant_id: UUID, current_user_id: UUID) -> None:
        now = self._now()
        grant = await self.get_grant(grant_id=grant_id)

        if grant.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Grant is already revoked",
            )
        if grant.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot revoke an expired grant",
            )
        if grant.granted_by_user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the grant creator can revoke the grant",
            )

        async with self.session.begin():
            ok = await self.repo.revoke_grant(grant_id=grant_id, now=now)
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Grant already revoked"
                )

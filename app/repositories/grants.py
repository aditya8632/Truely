from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.grant import Grant, Permission


class GrantsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def cleanup_expired_unrevoked_for_pair(
        self, *, granted_to_user_id: UUID, document_id: UUID, now: datetime
    ) -> int:
        stmt = (
            update(Grant)
            .where(
                Grant.granted_to_user_id == granted_to_user_id,
                Grant.document_id == document_id,
                Grant.revoked_at.is_(None),
                Grant.expires_at <= now,
            )
            .values(revoked_at=now)
        )
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)

    async def get_active_grant_for_pair(
        self, *, granted_to_user_id: UUID, document_id: UUID, now: datetime
    ) -> Grant | None:
        stmt = (
            select(Grant)
            .where(
                Grant.granted_to_user_id == granted_to_user_id,
                Grant.document_id == document_id,
                Grant.revoked_at.is_(None),
                Grant.expires_at > now,
            )
            .order_by(Grant.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_grant(
        self,
        *,
        document_id: UUID,
        granted_to_user_id: UUID,
        granted_by_user_id: UUID,
        permission: Permission,
        expires_at: datetime,
        created_at: datetime,
    ) -> Grant:
        grant = Grant(
            document_id=document_id,
            granted_to_user_id=granted_to_user_id,
            granted_by_user_id=granted_by_user_id,
            permission=permission,
            expires_at=expires_at,
            created_at=created_at,
            revoked_at=None,
        )
        self.session.add(grant)
        await self.session.flush()
        return grant

    async def get_grant_by_id(self, *, grant_id: UUID) -> Grant | None:
        stmt = select(Grant).where(Grant.id == grant_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_grants(
        self,
        *,
        document_id: UUID | None,
        granted_to_user_id: UUID | None,
        active_only: bool,
        now: datetime,
        limit: int,
        offset: int,
    ) -> tuple[list[Grant], int]:
        where_clauses: list[sa.ClauseElement] = []

        if document_id is not None:
            where_clauses.append(Grant.document_id == document_id)
        if granted_to_user_id is not None:
            where_clauses.append(Grant.granted_to_user_id == granted_to_user_id)
        if active_only:
            where_clauses.append(Grant.revoked_at.is_(None))
            where_clauses.append(Grant.expires_at > now)

        base_stmt = select(Grant).where(*where_clauses).order_by(Grant.created_at.desc())
        paged_stmt = base_stmt.limit(limit).offset(offset)

        count_stmt = select(func.count()).select_from(Grant).where(*where_clauses)

        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar_one())

        result = await self.session.execute(paged_stmt)
        items = list(result.scalars().all())

        return items, total

    async def revoke_grant(self, *, grant_id: UUID, now: datetime) -> bool:
        stmt = (
            update(Grant)
            .where(Grant.id == grant_id, Grant.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0

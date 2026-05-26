from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.schemas.grant import GrantCreate


@pytest.mark.parametrize(
    "expires_at",
    [
        # Naive datetime
        datetime.now() + timedelta(minutes=5),
        # Too soon
        datetime.now(UTC) + timedelta(seconds=30),
    ],
)
def test_grant_create_expires_at_validation(expires_at: datetime) -> None:
    with pytest.raises(ValidationError):
        GrantCreate(
            document_id=UUID("44444444-4444-4444-4444-444444444444"),
            granted_to_user_id=UUID("22222222-2222-2222-2222-222222222222"),
            permission="view",
            expires_at=expires_at,
        )


class FakeSession:
    @asynccontextmanager
    async def begin(self):
        yield


@dataclass
class FakeGrant:
    revoked_at: datetime | None
    expires_at: datetime
    granted_by_user_id: UUID


class FakeRepo:
    def __init__(self, *, now: datetime):
        self.now = now
        self.existing_calls = 0

    async def cleanup_expired_unrevoked_for_pair(self, *, granted_to_user_id, document_id, now):
        return 0

    async def get_active_grant_for_pair(self, *, granted_to_user_id, document_id, now):
        self.existing_calls += 1
        # First call simulates no existing active grant, subsequent calls simulate an active grant.
        if self.existing_calls >= 2:
            return FakeGrant(
                revoked_at=None,
                expires_at=self.now + timedelta(minutes=5),
                granted_by_user_id=UUID("11111111-1111-1111-1111-111111111111"),
            )
        return None

    async def create_grant(
        self,
        *,
        document_id,
        granted_to_user_id,
        granted_by_user_id,
        permission,
        expires_at,
        created_at,
    ):
        return FakeGrant(
            revoked_at=None, expires_at=expires_at, granted_by_user_id=granted_by_user_id
        )

    async def get_grant_by_id(self, *, grant_id):
        return FakeGrant(
            revoked_at=None,
            expires_at=self.now + timedelta(minutes=5),
            granted_by_user_id=UUID("11111111-1111-1111-1111-111111111111"),
        )

    async def revoke_grant(self, *, grant_id, now):
        return True


@pytest.mark.asyncio
async def test_duplicate_active_grant_prevention() -> None:
    from app.services.grants import GrantService

    now = datetime.now(UTC)
    service = GrantService(session=FakeSession(), now_provider=lambda: now)
    service.repo = FakeRepo(now=now)

    payload = GrantCreate(
        document_id=UUID("44444444-4444-4444-4444-444444444444"),
        granted_to_user_id=UUID("22222222-2222-2222-2222-222222222222"),
        permission="view",
        expires_at=now + timedelta(minutes=10),
    )

    # First insert allowed.
    grant = await service.create_grant(
        data=payload, current_user_id=UUID("11111111-1111-1111-1111-111111111111")
    )
    assert grant is not None

    # Second insert for the same pair should conflict.
    with pytest.raises(HTTPException) as excinfo:
        await service.create_grant(
            data=payload, current_user_id=UUID("11111111-1111-1111-1111-111111111111")
        )
    assert excinfo.value.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_revoke_authorization() -> None:
    from app.services.grants import GrantService

    now = datetime(2026, 1, 1, tzinfo=UTC)

    class Repo(FakeRepo):
        async def get_grant_by_id(self, *, grant_id):
            return FakeGrant(
                revoked_at=None,
                expires_at=now + timedelta(minutes=5),
                granted_by_user_id=UUID("11111111-1111-1111-1111-111111111111"),
            )

    service = GrantService(session=FakeSession(), now_provider=lambda: now)
    service.repo = Repo(now=now)

    with pytest.raises(HTTPException) as excinfo:
        await service.revoke_grant(
            grant_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            current_user_id=UUID("22222222-2222-2222-2222-222222222222"),
        )
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_revoke_expired_grant_handling() -> None:
    from app.services.grants import GrantService

    now = datetime(2026, 1, 1, tzinfo=UTC)

    class Repo(FakeRepo):
        async def get_grant_by_id(self, *, grant_id):
            return FakeGrant(
                revoked_at=None,
                expires_at=now - timedelta(seconds=1),
                granted_by_user_id=UUID("11111111-1111-1111-1111-111111111111"),
            )

    service = GrantService(session=FakeSession(), now_provider=lambda: now)
    service.repo = Repo(now=now)

    with pytest.raises(HTTPException) as excinfo:
        await service.revoke_grant(
            grant_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            current_user_id=UUID("11111111-1111-1111-1111-111111111111"),
        )
    assert excinfo.value.status_code == status.HTTP_400_BAD_REQUEST

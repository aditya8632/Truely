from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.db.models.grant import Permission


class GrantCreate(BaseModel):
    document_id: UUID
    granted_to_user_id: UUID
    permission: Permission
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")

        now = datetime.now(UTC)
        if v < now + timedelta(minutes=1):
            raise ValueError("expires_at must be at least 1 minute in the future")
        return v


class GrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    granted_to_user_id: UUID
    granted_by_user_id: UUID
    permission: Permission
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class GrantsListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[GrantRead]
    total: int
    limit: int
    offset: int


class GrantActiveCheck(BaseModel):
    active: bool

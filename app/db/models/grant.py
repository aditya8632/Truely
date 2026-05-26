from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.database import Base


class Permission(StrEnum):
    view = "view"
    edit = "edit"
    admin = "admin"


class Grant(Base):
    __tablename__ = "grants"
    __table_args__ = (
        sa.Index("ix_grants_document_id", "document_id"),
        sa.Index("ix_grants_granted_to_user_id", "granted_to_user_id"),
        sa.Index("ix_grants_expires_at", "expires_at"),
        # "Active" constraint strategy:
        # We use a partial unique index on non-revoked rows; the service will also mark
        # expired grants as revoked on grant creation to ensure the single-active behavior.
        sa.Index(
            "uq_active_grant_per_pair",
            "granted_to_user_id",
            "document_id",
            unique=True,
            postgresql_where=sa.text("revoked_at IS NULL"),
        ),
        {"schema": settings.schema_name},
    )

    id: Mapped[sa.UUID] = mapped_column(sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    document_id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True), sa.ForeignKey(f"{settings.schema_name}.documents.id"), nullable=False
    )
    granted_to_user_id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey(f"{settings.schema_name}.users.id"),
        nullable=False,
    )
    granted_by_user_id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey(f"{settings.schema_name}.users.id"),
        nullable=False,
    )

    permission: Mapped[Permission] = mapped_column(
        sa.Enum(Permission, name="permission_enum", schema=settings.schema_name),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )

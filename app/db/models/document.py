from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__: ClassVar[dict[str, str]] = {"schema": settings.schema_name}

    id: Mapped[sa.UUID] = mapped_column(sa.UUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(sa.String(length=255), unique=True, nullable=False)

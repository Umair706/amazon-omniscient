"""Base model and mixins for SQLAlchemy 2.0 ORM models."""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Timezone-aware timestamp type compatible with all SQLAlchemy versions.
# Use this instead of the deprecated ``TIMESTAMPTZ`` dialect type.
TIMESTAMPTZ = TIMESTAMP(timezone=True)


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

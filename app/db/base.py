"""
SQLAlchemy declarative base and shared model mixins.

All ORM models inherit from Base. Mixins provide reusable columns
(timestamps, soft delete) without inheritance pollution.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Inheriting from DeclarativeBase (SQLAlchemy 2.0 style) instead of
    the older `declarative_base()` function provides better type support
    and Mypy integration.
    """

    pass


class TimestampMixin:
    """
    Adds created_at and updated_at columns to any model.

    server_default=func.now() — the database sets the value, not Python.
    This is more reliable: it uses the database clock (one source of truth)
    and works correctly even when records are created outside SQLAlchemy.

    onupdate=func.now() — SQLAlchemy triggers this on every UPDATE.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Adds soft delete capability to a model.

    Soft delete: instead of deleting a row, set deleted_at to the current
    timestamp. The row remains in the database for audit trails, foreign
    key references, and recovery.

    IMPORTANT: Every query on a soft-deletable model must include
        .where(Model.deleted_at.is_(None))
    to exclude deleted records. The repository base handles this.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,  # Indexed because every query filters on this
    )

    @property
    def is_deleted(self) -> bool:
        """Convenience property — True if this record has been soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark this record as deleted. Call session.flush() after."""
        self.deleted_at = datetime.now(UTC)

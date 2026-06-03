from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.user import User


class Transaction(Base, TimestampMixin, SoftDeleteMixin):
    """
    The central resource of SpendWise — income and expense records.

    Design decisions:
    - Soft delete: transactions are never truly deleted for audit purposes.
      Reports include the full history including deleted transactions.
    - Decimal amount: NUMERIC(12, 2) — exact decimal arithmetic, no float.
    - Date (not datetime): transactions belong to a calendar date, not a
      specific moment. Storing datetime creates timezone complexity for no gain.
    - ARRAY tags: PostgreSQL native array type for tag storage.
      Alternative (junction table) is overkill for a simple tag list.
    """

    __tablename__: str = "transactions"

    # Table-level constraints and indexes
    __table_args__ = (
        # Composite index: almost every transaction query filters by user_id
        # and sorts or filters by date. This compound index serves both.
        Index(
            "ix_transactions_user_date",
            "user_id",
            "transaction_date",
            # No postgresql_where here — this is not a partial index
        ),
        # Index for category-based filtering and joins
        Index("ix_transactions_category", "category_id"),
        # Database-level check constraint: amount must always be positive.
        # This is the last line of defence — validation should catch this
        # earlier (Pydantic validator in schema), but the DB ensures it too.
        CheckConstraint("amount > 0", name="ck_transaction_positive_amount"),
        # The existing index on deleted_at from SoftDeleteMixin is a single-
        # column index. The compound index above also helps filter soft-deleted
        # rows when combined with user_id and date filters.
    )

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        # Indexed by the composite index above — no separate index needed
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        # ondelete="RESTRICT": cannot delete a category that has transactions.
        # This is intentional — force the user to reassign transactions first.
        # Contrast with user_id which uses CASCADE (delete user = delete everything).
    )

    # Core financial fields
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        # NUMERIC(precision, scale):
        # precision=12: total significant digits (e.g. 999,999,999.99)
        # scale=2: digits after the decimal point
        # Maximum storable: 9,999,999,999.99 — adequate for personal finance
        nullable=False,
    )

    description: Mapped[str] = mapped_column(String(500), nullable=False)

    transaction_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        # Not indexed individually — covered by the composite (user_id, date) index
    )

    transaction_type: Mapped[str] = mapped_column(
        String(10),
        # Storing the enum value as a string (not PostgreSQL ENUM type).
        # Pros: no migration needed when enum values change, simpler schema.
        # Cons: no database-level constraint (the CheckConstraint below handles this).
        nullable=False,
    )

    # Optional fields
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # TEXT: unlimited length in PostgreSQL. Notes can be long.

    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        # PostgreSQL-specific: stores an array of strings in a single column.
        # Enables queries like: WHERE 'groceries' = ANY(tags)
        # Alternative: separate tags table with junction table. Overkill here.
        server_default="{}",  # Empty array as default
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="transactions",
        lazy="noload",
    )

    category: Mapped[Category] = relationship(
        "Category",
        back_populates="transactions",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self.id!r}, amount={self.amount!r}, "
            f"type={self.transaction_type!r}, user_id={self.user_id!r})"
        )

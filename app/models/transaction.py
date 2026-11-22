from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.user import User


class Transaction(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__: str = "transactions"

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transaction_positive_amount"),
        CheckConstraint("type IN ('income', 'expense')", name="ck_transaction_type"),
        Index("ix_transactions_user_date", "user_id", "transaction_date"),
        Index(
            "ix_transactions_active_user_date_id",
            "user_id",
            "transaction_date",
            "id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_transactions_active",
            "id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)

    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        server_default="{}",
        nullable=False,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="transactions",
        lazy="noload",
    )

    category: Mapped[Category | None] = relationship(
        "Category",
        back_populates="transactions",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self.id!r}, amount={self.amount!r}, "
            f"type={self.type!r}, user_id={self.user_id!r})"
        )

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.user import User


class Category(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__: str = "categories"

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_category_user_name"),
        CheckConstraint(
            "type IN ('income', 'expense', 'both')", name="ck_category_type"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    type: Mapped[str] = mapped_column(
        String(10),
        server_default="both",
        default="both",
        nullable=False,
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        default=False,
        nullable=False,
    )

    user: Mapped[User | None] = relationship(
        "User",
        back_populates="categories",
        lazy="noload",
    )

    # Financial records must never be silently cascade deleted
    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction",
        back_populates="category",
        cascade="save-update, merge",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"Category(id={self.id!r}, name={self.name!r}, user_id={self.user_id!r})"

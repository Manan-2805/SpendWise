from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.user import User


class Category(Base, TimestampMixin, SoftDeleteMixin):
    """
    User-owned expense/income categories.

    Each user has their own set of categories — categories are not shared
    between users. This is enforced by the user_id foreign key.

    The unique constraint (user_id, name) ensures a user cannot have two
    categories with the same name, but different users can reuse names
    (e.g. everyone can have a "Food" category).
    """

    __tablename__: str = "categories"

    # Table-level constraints and indexes
    __table_args__ = (
        # Composite unique constraint: same user cannot have two categories
        # with the same name. Different users can both have "Food".
        UniqueConstraint(
            "user_id",
            "name",
            name="uq_category_user_name",  # Named constraints are easier to debug
        ),
        # Note: additional indexes can also go here as Index() objects
    )

    # Columns
    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ondelete="CASCADE": if the user is deleted, their categories are too.
    # This matches the relationship cascade above — they must agree.

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    icon: Mapped[str | None] = mapped_column(
        String(50),  # Emoji or icon identifier
        nullable=True,
    )

    color: Mapped[str | None] = mapped_column(
        String(7),  # "#FF5733" — hex color with # prefix, 7 chars
        nullable=True,
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="categories",
        lazy="noload",
    )

    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction",
        back_populates="category",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"Category(id={self.id!r}, name={self.name!r}, user_id={self.user_id!r})"

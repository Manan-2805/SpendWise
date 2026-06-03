from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.transaction import Transaction


class User(Base, TimestampMixin, SoftDeleteMixin):
    """
    Represents a registered SpendWise user.

    Mixin inheritance order matters for Python's MRO:
    Base first (provides __tablename__ scanning and metadata),
    then mixins (they only add columns, no conflicting methods).
    """

    __tablename__: str = "users"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    # SQLAlchemy generates: id SERIAL PRIMARY KEY (PostgreSQL)
    # SERIAL is an alias for INTEGER with a SEQUENCE — auto-incrementing.

    # Identity fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,  # Enforced at database level: UNIQUE constraint
        index=True,  # Additional B-tree index for fast lookups
        nullable=False,
    )
    # Note: unique=True already creates an index in PostgreSQL.
    # Specifying index=True as well is redundant but explicit.
    # In production, unique=True is sufficient.

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    # Security
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    # bcrypt hashes are always 60 characters. String(255) gives headroom
    # if we ever switch hashing algorithms.
    # NEVER store plain text passwords. NEVER store reversibly encrypted passwords.
    # Only store the bcrypt hash.

    # Status flags
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default="true",
        nullable=False,
    )

    refresh_token_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    # is_active=False: account suspended or deactivated.
    # Different from soft delete: soft-deleted users are completely gone.
    # Inactive users can be reactivated.

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
    )
    # is_verified=False: email verification pending.
    # Some endpoints require is_verified=True (see UnverifiedEmailError).

    # Relationships
    categories: Mapped[list[Category]] = relationship(
        "Category",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",  # Never load automatically — always explicit
    )
    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r}, username={self.username!r})"

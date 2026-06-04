from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.audit import AuditLog
    from app.models.auth import OAuthAccount, RefreshToken
    from app.models.category import Category
    from app.models.transaction import Transaction


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__: str = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", default=True, nullable=False
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )

    verification_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reset_password_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    cache_version: Mapped[int] = mapped_column(
        Integer, server_default="0", default=0, nullable=False
    )

    categories: Mapped[list[Category]] = relationship(
        "Category",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        "OAuthAccount",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r}, username={self.username!r})"

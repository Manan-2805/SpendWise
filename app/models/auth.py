from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class OAuthAccount(Base, TimestampMixin):
    __tablename__: str = "oauth_accounts"

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_provider_account"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)

    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped[User] = relationship(
        "User",
        back_populates="oauth_accounts",
        lazy="noload",
    )


class RefreshToken(Base):
    __tablename__: str = "refresh_tokens"

    __table_args__ = (
        Index("ix_refresh_tokens_jti", "jti", unique=True),
        Index("ix_refresh_tokens_family_id", "family_id"),
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(36), nullable=False)
    family_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    rotated_from_id: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(
        "User",
        back_populates="refresh_tokens",
        lazy="noload",
    )

    rotated_from: Mapped[RefreshToken | None] = relationship(
        "RefreshToken",
        remote_side=[id],
        lazy="noload",
    )

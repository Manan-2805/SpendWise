from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

from .user import User


class OAuthAccount(Base, TimestampMixin):
    __tablename__: str = "oauth_accounts"

    __table_args__ = (
        # A user can only have ONE Google account linked
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "google"
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # We store the provider's access token to make API calls on user's behalf later
    access_token: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="oauth_accounts")


class RefreshToken(Base):
    """
    Stores hashed refresh tokens for revocation and rotation tracking.
    """

    __tablename__ = "refresh_tokens"

    __table_args__ = (
        # Fast lookups when validating a token hash
        Index("ix_refresh_tokens_token_hash", "token_hash"),
        # Fast lookups when revoking all tokens for a user
        Index("ix_refresh_tokens_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # We store the SHA-256 hash of the JWT, not the JWT itself
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # The unique 'jti' claim from the JWT, used for Token Family tracking
    jti: Mapped[str] = mapped_column(String(36), nullable=False)

    # When this token expires (matches the JWT exp claim)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Revocation flag. If True, this token has been used or manually revoked.
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamp of creation/rotation
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationship
    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")

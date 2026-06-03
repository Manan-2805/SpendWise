from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import Result, Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.auth import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest

logger = structlog.get_logger()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db: AsyncSession = db

    async def register(self, data: RegisterRequest) -> User:
        """Register a new user."""
        # 1. Check if email exists
        stmt: Select[tuple[User]] = select(User).where(User.email == data.email)
        result: Result[tuple[User]] = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise EmailAlreadyRegisteredError(data.email)

        # 2. Create user
        new_user = User(
            email=data.email,
            username=data.username,
            hashed_password=hash_password(data.password),
            is_active=True,
            is_verified=False,  # Require email verification in production
        )
        self.db.add(new_user)
        await self.db.flush()  # Get ID

        logger.info("user_registered", user_id=new_user.id, email=new_user.email)
        return new_user

    async def authenticate(self, email: str, password: str) -> tuple[str, str, User]:
        """
        Verify credentials and issue token pair.
        Returns: (access_token, refresh_token, user)
        """
        stmt: Select[tuple[User]] = select(User).where(User.email == email)
        result: Result[tuple[User]] = await self.db.execute(stmt)
        user: User | None = result.scalar_one_or_none()

        # CRITICAL: Use constant-time verification logic internally handled by pwdlib
        # Do NOT short-circuit (e.g., if not user: return False) to prevent timing attacks
        # on user enumeration. We verify a dummy hash if user doesn't exist.
        if not user:
            # Verify against a dummy hash to keep response time consistent
            verify_password(
                password, "$2b$12$W9G7XyZ12345678901234567890123456789012345678901234"
            )
            raise InvalidCredentialsError()

        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        # Generate tokens
        access_token: str = create_access_token(subject=user.id)
        refresh_token: str = create_refresh_token(subject=user.id)

        # Store hashed refresh token in DB
        payload: dict[str, Any] = decode_token(refresh_token)
        rt_record = RefreshToken(
            token_hash=hash_refresh_token(refresh_token),
            user_id=user.id,
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
        self.db.add(rt_record)
        await self.db.flush()

        logger.info("user_logged_in", user_id=user.id)
        return access_token, refresh_token, user

    async def refresh_tokens(self, raw_refresh_token: str) -> tuple[str, str]:
        """
        Refresh Token Rotation with Reuse Detection.
        """
        # 1. Decode and validate JWT signature/expiry
        try:
            payload: dict[str, Any] = decode_token(raw_refresh_token)
        except Exception as e:
            raise InvalidTokenError("Invalid refresh token") from e

        if payload.get("type") != "refresh":
            raise InvalidTokenError("Token substitution attempt detected")

        token_hash = hash_refresh_token(raw_refresh_token)

        # 2. Find token in DB
        stmt: Select[tuple[RefreshToken]] = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash
        )
        result: Result[tuple[RefreshToken]] = await self.db.execute(stmt)
        db_token: RefreshToken | None = result.scalar_one_or_none()

        if not db_token:
            raise InvalidTokenError("Refresh token not found or already revoked")

        # 3. REUSE DETECTION (The Nuclear Option)
        if db_token.is_revoked:
            # An attacker is trying to use an already-rotated token!
            # Revoke ALL tokens for this user immediately.
            logger.warning(
                "refresh_token_reuse_detected",
                user_id=db_token.user_id,
                jti=db_token.jti,
            )
            await self.db.execute(
                delete(RefreshToken).where(RefreshToken.user_id == db_token.user_id)
            )
            await self.db.commit()
            raise InvalidTokenError("Token reuse detected. All sessions revoked.")

        # 4. Rotate: Revoke old token
        db_token.is_revoked = True
        await self.db.flush()

        # 5. Issue new pair
        user_id: int = db_token.user_id
        new_access: str = create_access_token(subject=user_id)
        new_refresh: str = create_refresh_token(subject=user_id)

        # 6. Store new refresh token
        new_payload: dict[str, Any] = decode_token(new_refresh)
        new_rt_record = RefreshToken(
            token_hash=hash_refresh_token(new_refresh),
            user_id=user_id,
            jti=new_payload["jti"],
            expires_at=datetime.fromtimestamp(new_payload["exp"], tz=UTC),
        )
        self.db.add(new_rt_record)
        await self.db.flush()

        return new_access, new_refresh

    async def revoke_user_tokens(self, user_id: int) -> None:
        """Logout: Delete all active refresh tokens for the user."""
        await self.db.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        await self.db.flush()
        logger.info("user_logged_out", user_id=user_id)

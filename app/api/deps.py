from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    InactiveUserError,
    UnverifiedEmailError,
)
from app.db.session import AsyncSessionLocal
from app.models.user import User

from ..core.security import decode_token

# This scheme is used for OpenAPI docs (Swagger UI "Authorize" button)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides one AsyncSession per HTTP request.

    The session lifecycle:
    1. Created at the start of the request (when Depends(get_db) resolves)
    2. Yielded to the route handler (and all dependencies that use it)
    3. On success: committed
    4. On any exception: rolled back
    5. Closed (returned to the pool) after the response is sent

    Using `async with AsyncSessionLocal() as session` is equivalent to:
        session = AsyncSessionLocal()
        try:
            yield session
        finally:
            await session.close()  # returns connection to pool

    We add explicit commit/rollback on top.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    request: Request,
    token_from_header: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract user from HttpOnly Cookie OR Authorization Header.
    """
    token = None

    # Priority 1: HttpOnly Cookie (Web clients)
    if "access_token" in request.cookies:
        token = request.cookies["access_token"]
    # Priority 2: Bearer Header (Mobile/Swagger)
    elif token_from_header:
        token = token_from_header

    if not token:
        raise AuthenticationError("Not authenticated")

    try:
        payload: dict[str, Any] = decode_token(token)
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        sub: Any | None = payload.get("sub")
        if sub is None:
            raise AuthenticationError("Token missing subject")
        user_id = int(str(sub))
    except Exception as e:
        raise AuthenticationError("Invalid or expired token") from e

    stmt = select(User).where(
        User.id == user_id, User.is_active, User.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    user: User | None = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("User not found or inactive")

    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    """Second-level dependency — requires active flag."""
    if not user.is_active:
        raise InactiveUserError()
    return user


async def get_current_verified_user(
    user: User = Depends(get_current_active_user),
) -> User:
    """Third-level dependency — requires email verification."""
    if not user.is_verified:
        raise UnverifiedEmailError()
    return user

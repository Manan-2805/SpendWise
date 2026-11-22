from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AccessDeniedError,
    AuthenticationError,
    InactiveUserError,
    UnverifiedEmailError,
)
from app.core.security import verify_token
from app.db.session import AsyncSessionLocal, run_after_commit
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides one AsyncSession per HTTP request.
    Commit validated responses before they are sent.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
            await run_after_commit(session)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def require_cookie_origin(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    trusted = {str(request.base_url).rstrip("/"), *settings.CORS_ORIGINS}
    fetch_site = request.headers.get("sec-fetch-site")
    if (origin and origin not in trusted) or (
        not origin and fetch_site in {"cross-site", "same-site"}
    ):
        raise AccessDeniedError("Untrusted origin for cookie authentication")


async def get_current_user(
    request: Request,
    token_from_header: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> User:
    """
    Extract user from HttpOnly Cookie OR Authorization Header.
    """
    token = token_from_header or request.cookies.get("access_token")
    if token and not token_from_header:
        require_cookie_origin(request)

    if not token:
        raise AuthenticationError("Not authenticated")

    try:
        payload = verify_token(token, expected_type="access")
        sub = payload.get("sub")
        if sub is None:
            raise AuthenticationError("Token missing subject")
        user_id = int(str(sub))
    except Exception as e:
        raise AuthenticationError("Invalid or expired token") from e

    stmt = select(User).where(
        User.id == user_id, User.is_active, User.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or payload.get("auth_version", 0) != (user.auth_version or 0):
        raise AuthenticationError("Session expired or user inactive")

    request.state.user = user
    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    """Second-level dependency requiring user to be active."""
    if not user.is_active:
        raise InactiveUserError()
    return user


async def get_current_verified_user(
    user: User = Depends(get_current_active_user),
) -> User:
    """Third-level dependency requiring email verification."""
    if not user.is_verified:
        raise UnverifiedEmailError()
    return user

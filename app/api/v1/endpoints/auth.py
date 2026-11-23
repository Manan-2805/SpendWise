from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_cookie_origin
from app.core.auth import oauth
from app.core.config import settings
from app.core.exceptions import (
    InvalidTokenError,
)
from app.core.rate_limit import limiter
from app.core.security import clear_auth_cookies, set_auth_cookies
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth import AuthService

router = APIRouter()


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
async def register(
    request: Request,
    response: Response,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db, scope="function"),
) -> TokenResponse:
    """Register a new user, issue tokens, set HttpOnly cookies, and queue verification email."""
    auth_service = AuthService(db)
    user = await auth_service.register(data)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    access_token, refresh_token, _ = await auth_service.authenticate(
        data.email, data.password, ip_address=ip_address, user_agent=user_agent
    )

    await auth_service.resend_verification(user.email)

    set_auth_cookies(response, access_token, refresh_token)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",  # nosec B106
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db, scope="function"),
) -> TokenResponse:
    """Log in with email and password, returning tokens and setting HttpOnly cookies."""
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    access_token, refresh_token, _ = await auth_service.login(
        data.email, data.password, ip_address=ip_address, user_agent=user_agent
    )

    set_auth_cookies(response, access_token, refresh_token)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",  # nosec B106
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db, scope="function"),
) -> TokenResponse:
    """Rotate refresh token to obtain a new access/refresh token pair."""
    token = data.refresh_token if data else None
    if not token and (token := request.cookies.get("refresh_token")):
        require_cookie_origin(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required",
        )

    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    try:
        access_token, new_refresh_token = await auth_service.refresh_tokens(
            token, ip_address=ip_address, user_agent=user_agent
        )
        set_auth_cookies(response, access_token, new_refresh_token)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",  # nosec B106
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except InvalidTokenError:
        request.state.clear_auth_cookies = True
        raise


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> dict[str, str]:
    """Revoke all active tokens for the user and clear HttpOnly cookies."""
    auth_service = AuthService(db)
    await auth_service.revoke_user_tokens(current_user.id)
    clear_auth_cookies(response)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current authenticated user's profile."""
    return current_user


@router.post("/change-password")
@limiter.limit("3/minute")
async def change_password(
    request: Request,  # noqa: ARG001
    response: Response,
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> dict[str, str]:
    """Change user password, revoke all sessions, and clear cookies."""
    auth_service = AuthService(db)
    await auth_service.change_password(
        current_user.id, data.current_password, data.new_password
    )
    clear_auth_cookies(response)
    return {"message": "Password changed successfully. Please log in again."}


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,  # noqa: ARG001
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db, scope="function"),
) -> dict[str, str]:
    """Request a password reset link to be sent to the email."""
    auth_service = AuthService(db)
    await auth_service.forgot_password(data.email)
    return {
        "message": "If the email is registered, a password reset link has been sent."
    }


@router.post("/reset-password")
@limiter.limit("3/minute")
async def reset_password(
    request: Request,  # noqa: ARG001
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db, scope="function"),
) -> dict[str, str]:
    """Reset the password using the provided reset token."""
    auth_service = AuthService(db)
    await auth_service.reset_password(data.token, data.new_password)
    return {"message": "Password reset successfully. Please log in again."}


@router.get("/verify-email")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db, scope="function"),
) -> dict[str, str]:
    """Verify email address using the token received in the verification email."""
    auth_service = AuthService(db)
    await auth_service.verify_email(token)
    return {"message": "Email verified successfully."}


@router.post("/resend-verification")
@limiter.limit("2/minute")
async def resend_verification(
    request: Request,  # noqa: ARG001
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> dict[str, str]:
    """Resend email verification link for the current user."""
    auth_service = AuthService(db)
    await auth_service.resend_verification(current_user.email)
    return {"message": "Verification email resent if user is not verified."}


@router.get("/google")
@limiter.limit("5/minute")
async def google_login(
    request: Request,
) -> Any:
    """Redirect to Google OAuth authorization portal."""
    if not settings.GOOGLE_OAUTH_ENABLED:
        raise HTTPException(status_code=400, detail="Google OAuth is not enabled")
    redirect_uri = settings.GOOGLE_REDIRECT_URI or str(
        request.url_for("google_callback")
    )
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,  # noqa: ARG001
    db: AsyncSession = Depends(get_db, scope="function"),
) -> Any:
    """Handle callback from Google, authenticating and linking accounts."""
    if not settings.GOOGLE_OAUTH_ENABLED:
        raise HTTPException(status_code=400, detail="Google OAuth is not enabled")
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail="Google authentication failed"
        ) from e

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(
            status_code=400, detail="Could not retrieve user info from Google"
        )

    email = user_info.get("email")
    username = user_info.get("name") or email.split("@")[0]
    provider_account_id = user_info.get("sub")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    auth_service = AuthService(db)
    access_token, refresh_token, _user = await auth_service.login_or_register_oauth(
        provider="google",
        provider_account_id=provider_account_id,
        email=email,
        username=username,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    token_resp = TokenResponse(
        access_token=access_token,
        token_type="bearer",  # nosec B106
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    json_response = JSONResponse(content=token_resp.model_dump())
    set_auth_cookies(json_response, access_token, refresh_token)
    return json_response

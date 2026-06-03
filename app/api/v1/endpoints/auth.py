from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth import AuthService
from app.services.user import UserService

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new user."""
    try:
        user_service = UserService(db)
        user: UserResponse = await user_service.create(data)
        return user
    except EmailAlreadyRegisteredError as e:
        raise HTTPException(status_code=409, detail=e.message) from e


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> tuple[str, str, User]:
    """Authenticate user and return access token."""
    auth_service = AuthService(db)
    try:
        tokens: tuple[str, str, User] = await auth_service.authenticate(
            data.email, data.password
        )
        return tokens
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail="Invalid email or password") from e


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> tuple[str, str]:
    """Get new access token using refresh token."""
    auth_service = AuthService(db)
    tokens: tuple[str, str] = await auth_service.refresh_tokens(data.refresh_token)
    return tokens


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Log out — revokes current user's refresh tokens."""
    auth_service = AuthService(db)
    await auth_service.revoke_user_tokens(current_user.id)
    return {"message": "Successfully logged out"}

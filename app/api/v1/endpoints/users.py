from fastapi import APIRouter, Depends, Request, status
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.cache import versioned_key_builder
from app.models.user import User
from app.schemas.auth import PasswordChangeRequest
from app.schemas.user import UserResponse, UserUpdate
from app.services.user import UserService

router = APIRouter()


@router.get("/me", response_model=UserResponse)
@cache(expire=3600, key_builder=versioned_key_builder)
async def get_me(
    _: Request,
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Get current authenticated user's profile."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update current user's profile."""
    user_service = UserService(db)
    updated_user: UserResponse = await user_service.update(current_user.id, data)
    return updated_user


@router.post("/me/password")
async def change_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Change current user's password."""
    user_service = UserService(db)
    await user_service.change_password(
        current_user.id,
        data.current_password,
        data.new_password,
    )
    return {"message": "Password changed successfully"}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete current user's account."""
    user_service = UserService(db)
    await user_service.soft_delete(current_user.id)

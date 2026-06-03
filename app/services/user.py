from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    UsernameAlreadyTakenError,
    UserNotFoundError,
)
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserResponse, UserUpdate


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = UserRepository(db)

    async def create(self, data: RegisterRequest) -> UserResponse:
        """Register a new user."""
        # Check uniqueness
        existing_email: User | None = await self.repo.get_by_email(data.email)
        if existing_email:
            raise EmailAlreadyRegisteredError(data.email)

        existing_username: User | None = await self.repo.get_by_username(data.username)
        if existing_username:
            raise UsernameAlreadyTakenError(data.username)

        # Hash password
        hashed: str = hash_password(data.password)

        # Create user
        user: User = await self.repo.create(
            email=data.email.lower(),
            username=data.username.lower(),
            hashed_password=hashed,
            is_active=True,
            is_verified=False,
        )
        return UserResponse.model_validate(user)

    async def get_by_id(self, user_id: int) -> UserResponse:
        user: User | None = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id=user_id)
        return UserResponse.model_validate(user)

    async def get_by_email(self, email: str) -> UserResponse:
        user: User | None = await self.repo.get_by_email(email)
        if not user:
            raise UserNotFoundError(email=email)
        return UserResponse.model_validate(user)

    async def update(self, user_id: int, data: UserUpdate) -> UserResponse:
        """Update user profile (username, email)."""
        # If email is being changed, check uniqueness
        if data.email:
            existing: User | None = await self.repo.get_by_email(data.email)
            if existing and existing.id != user_id:
                raise EmailAlreadyRegisteredError(data.email)
        # If username is being changed, check uniqueness
        if data.username:
            existing = await self.repo.get_by_username(data.username)
            if existing and existing.id != user_id:
                raise UsernameAlreadyTakenError(data.username)

        update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
        user: User | None = await self.repo.update(user_id, **update_data)
        if not user:
            raise UserNotFoundError(user_id=user_id)
        return UserResponse.model_validate(user)

    async def soft_delete(self, user_id: int) -> None:
        deleted: bool = await self.repo.soft_delete(user_id)
        if not deleted:
            raise UserNotFoundError(user_id=user_id)

    async def change_password(
        self, user_id: int, current_password: str, new_password: str
    ) -> None:
        user: User | None = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id=user_id)
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError()
        new_hashed: str = hash_password(new_password)
        await self.repo.update(user_id, hashed_password=new_hashed)

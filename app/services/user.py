import asyncio
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
from app.repositories.auth import AuthRepository
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserResponse, UserUpdate
from app.services.audit import AuditService


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)
        self.audit_service = AuditService(db)

    async def create(self, data: RegisterRequest) -> UserResponse:
        """Register a new user."""
        user = await self.create_user(data)
        return UserResponse.model_validate(user)

    async def create_user(self, data: RegisterRequest) -> User:
        """Create a new user and return the raw model (for service-to-service calls)."""
        existing_email: User | None = await self.repo.get_by_email(data.email)
        if existing_email:
            raise EmailAlreadyRegisteredError(data.email)

        existing_username: User | None = await self.repo.get_by_username(data.username)
        if existing_username:
            raise UsernameAlreadyTakenError(data.username)

        hashed = await asyncio.to_thread(hash_password, data.password)

        user: User = await self.repo.create(
            email=data.email.lower(),
            username=data.username.lower(),
            hashed_password=hashed,
            is_active=True,
            is_verified=False,
        )

        await self.audit_service.log_action(
            action="USER_CREATED",
            resource_type="User",
            resource_id=user.id,
            user_id=user.id,
        )
        return user

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
        if data.email:
            existing: User | None = await self.repo.get_by_email(data.email)
            if existing and existing.id != user_id:
                raise EmailAlreadyRegisteredError(data.email)
        if data.username:
            existing = await self.repo.get_by_username(data.username)
            if existing and existing.id != user_id:
                raise UsernameAlreadyTakenError(data.username)

        update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
        if data.username:
            update_data["username"] = data.username.lower()
        if data.email:
            update_data["email"] = data.email.lower()
            current = await self.repo.get_by_id(user_id)
            if current and current.email != update_data["email"]:
                await AuthRepository(self.db).invalidate_sessions(user_id)
                update_data.update(
                    is_verified=False,
                    verification_token=None,
                    verification_token_expires_at=None,
                    reset_password_token=None,
                    reset_token_expires_at=None,
                )
        user: User | None = await self.repo.update(user_id, **update_data)
        if not user:
            raise UserNotFoundError(user_id=user_id)

        await self.audit_service.log_action(
            action="USER_UPDATED",
            resource_type="User",
            resource_id=user.id,
            user_id=user.id,
            new_values={"fields": sorted(data.model_fields_set)},
        )
        return UserResponse.model_validate(user)

    async def soft_delete(self, user_id: int) -> None:
        deleted: bool = await self.repo.soft_delete(user_id)
        if not deleted:
            raise UserNotFoundError(user_id=user_id)

        await self.audit_service.log_action(
            action="USER_DELETED",
            resource_type="User",
            resource_id=user_id,
            user_id=user_id,
        )

    async def change_password(
        self, user_id: int, current_password: str, new_password: str
    ) -> None:
        user: User | None = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id=user_id)
        if not user.hashed_password or not await asyncio.to_thread(
            verify_password, current_password, user.hashed_password
        ):
            raise InvalidCredentialsError()
        new_hashed = await asyncio.to_thread(hash_password, new_password)
        await self.repo.update(user_id, hashed_password=new_hashed)

        await self.audit_service.log_action(
            action="PASSWORD_CHANGED",
            resource_type="User",
            resource_id=user_id,
            user_id=user_id,
        )

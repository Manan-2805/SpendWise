import asyncio
import secrets
import string
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_token,
)
from app.db.session import after_commit
from app.models.user import User
from app.repositories.auth import AuthRepository
from app.schemas.auth import RegisterRequest
from app.services.audit import AuditService
from app.services.user import UserService

logger = structlog.get_logger()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.auth_repo = AuthRepository(db)
        self.user_service = UserService(db)
        self.audit_service = AuditService(db)

    async def register(self, data: RegisterRequest) -> User:
        """Register a new user, delegating to UserService."""
        user = await self.user_service.create_user(data)
        return user

    async def authenticate(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, User]:
        """
        Verify credentials, issue access/refresh token family, audit results.
        """
        user = await self.user_service.repo.get_by_email(email)

        if not user:
            await asyncio.to_thread(
                verify_password,
                password,
                "$2b$12$KM/voy8TSax1XOEtR6/dOufvPnHAFSNSg99mLyVAHh8D4cG7Y0og2",
            )
            await self.audit_service.log_action(
                action="LOGIN_FAILED",
                resource_type="User",
                resource_id="none",
                new_values={"email": email, "reason": "user_not_found"},
            )
            raise InvalidCredentialsError()

        if not user.hashed_password or not await asyncio.to_thread(
            verify_password, password, user.hashed_password
        ):
            await self.audit_service.log_action(
                action="LOGIN_FAILED",
                resource_type="User",
                resource_id=user.id,
                user_id=user.id,
                new_values={"reason": "invalid_password"},
            )
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        checked_hash = user.hashed_password
        active_user = await self.auth_repo.lock_active_user(user.id)
        if not active_user or active_user.hashed_password != checked_hash:
            raise InvalidCredentialsError()

        access_token = create_access_token(
            subject=user.id, auth_version=active_user.auth_version or 0
        )
        refresh_token, jti = create_refresh_token(subject=user.id)

        token_hash = hash_refresh_token(refresh_token)
        payload = verify_token(refresh_token, expected_type="refresh")
        expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)

        await self.auth_repo.create_refresh_token(
            user_id=user.id,
            jti=jti,
            family_id=jti,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.audit_service.log_action(
            action="LOGIN_SUCCESS",
            resource_type="User",
            resource_id=user.id,
            user_id=user.id,
        )
        return access_token, refresh_token, user

    async def refresh_tokens(
        self,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """
        Refresh Token Rotation with Reuse Detection.
        """
        try:
            payload = verify_token(raw_refresh_token, expected_type="refresh")
            user_id = int(payload["sub"])
        except Exception as e:
            raise InvalidTokenError("Invalid refresh token") from e

        user = await self.auth_repo.lock_active_user(user_id)
        token_hash = hash_refresh_token(raw_refresh_token)
        db_token = await self.auth_repo.get_by_hash(token_hash)
        if not user or not db_token or db_token.user_id != user_id:
            raise InvalidTokenError("Refresh token not found or already revoked")

        if db_token.revoked_at is not None:
            await self.auth_repo.revoke_family(db_token.family_id)
            await self.audit_service.log_action(
                action="TOKEN_REVOKED",
                resource_type="RefreshToken",
                resource_id=db_token.jti,
                user_id=db_token.user_id,
                old_values={
                    "family_id": db_token.family_id,
                    "reason": "token_reuse_detected",
                },
            )
            await self.db.commit()
            raise InvalidTokenError("Token reuse detected. Session revoked.")

        if db_token.expires_at < datetime.now(UTC):
            raise InvalidTokenError("Refresh token has expired")

        # Revoke the old token
        await self.auth_repo.revoke_token(db_token.jti)

        # Issue a new pair
        new_access = create_access_token(
            subject=user_id, auth_version=user.auth_version or 0
        )
        new_refresh, new_jti = create_refresh_token(subject=user_id)
        new_token_hash = hash_refresh_token(new_refresh)
        new_payload = verify_token(new_refresh, expected_type="refresh")
        new_expires_at = datetime.fromtimestamp(new_payload["exp"], tz=UTC)

        await self.auth_repo.create_refresh_token(
            user_id=user_id,
            jti=new_jti,
            family_id=db_token.family_id,
            token_hash=new_token_hash,
            expires_at=new_expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            rotated_from_id=db_token.id,
        )
        return new_access, new_refresh

    async def revoke_user_tokens(self, user_id: int) -> None:
        """Logout: Delete all active refresh tokens for the user."""
        await self.auth_repo.invalidate_sessions(user_id)
        await self.audit_service.log_action(
            action="TOKEN_REVOKED",
            resource_type="RefreshToken",
            resource_id="all",
            user_id=user_id,
        )

    async def change_password(
        self, user_id: int, current_password: str, new_password: str
    ) -> None:
        """Change user password and revoke all active refresh tokens."""
        if not await self.auth_repo.lock_active_user(user_id):
            raise InvalidCredentialsError()
        await self.user_service.change_password(user_id, current_password, new_password)
        await self.auth_repo.invalidate_sessions(user_id)

    async def login_or_register_oauth(
        self,
        provider: str,
        provider_account_id: str,
        email: str,
        username: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, User]:
        """Link or create account via OAuth, then issue token pair and audit log."""
        oauth_acc = await self.auth_repo.get_oauth_account(
            provider, provider_account_id
        )
        if oauth_acc:
            user = await self.user_service.repo.get_by_id(oauth_acc.user_id)
            if not user or user.deleted_at is not None:
                raise InvalidCredentialsError("OAuth account user not found")
        else:
            user = await self.user_service.repo.get_by_email(email)
            if not user:
                base_username = username or email.split("@")[0]
                existing_username = await self.user_service.repo.get_by_username(
                    base_username
                )
                if existing_username:
                    base_username = f"{base_username}_{''.join(secrets.choice(string.digits) for _ in range(4))}"

                user = await self.user_service.repo.create(
                    email=email.lower(),
                    username=base_username.lower(),
                    hashed_password=None,
                    is_active=True,
                    is_verified=True,
                )

                await self.audit_service.log_action(
                    action="USER_CREATED",
                    resource_type="User",
                    resource_id=user.id,
                    user_id=user.id,
                )

            await self.auth_repo.create_oauth_account(
                user_id=user.id,
                provider=provider,
                provider_account_id=provider_account_id,
            )
            await self.audit_service.log_action(
                action="OAUTH_LINKED",
                resource_type="OAuthAccount",
                resource_id=provider_account_id,
                user_id=user.id,
            )

        if not user.is_active:
            raise InactiveUserError()

        # Issue tokens
        access_token = create_access_token(
            subject=user.id, auth_version=user.auth_version or 0
        )
        refresh_token, jti = create_refresh_token(subject=user.id)
        token_hash = hash_refresh_token(refresh_token)
        payload = verify_token(refresh_token, expected_type="refresh")
        expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)

        await self.auth_repo.create_refresh_token(
            user_id=user.id,
            jti=jti,
            family_id=jti,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.audit_service.log_action(
            action="LOGIN_SUCCESS",
            resource_type="User",
            resource_id=user.id,
            user_id=user.id,
            new_values={"method": f"oauth_{provider}"},
        )
        return access_token, refresh_token, user

    async def forgot_password(self, email: str) -> None:
        """Generate reset token, trigger reset email Celery task, and audit request."""
        user = await self.user_service.repo.get_by_email(email)
        if not user:
            return

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        await self.user_service.repo.update(
            user.id,
            reset_password_token=hash_refresh_token(token),
            reset_token_expires_at=expires_at,
        )

        from app.worker.tasks import send_password_reset_email

        ctx = structlog.contextvars.get_contextvars()

        async def enqueue() -> None:
            await asyncio.to_thread(
                send_password_reset_email.apply_async,
                args=(user.id, token),
                kwargs={"correlation_id": ctx.get("correlation_id")},
                argsrepr="(<account>, <redacted>)",
                expires=3600,
            )

        after_commit(self.db, enqueue)

        await self.audit_service.log_action(
            action="FORGOT_PASSWORD_REQUESTED",
            resource_type="User",
            resource_id=user.id,
            user_id=user.id,
        )

    async def reset_password(self, token: str, new_password: str) -> None:
        """Validate reset token, update password, and revoke all active refresh tokens."""
        user = await self.user_service.repo.get_by_reset_token(token)
        if not user:
            raise InvalidTokenError("Invalid or expired password reset token")

        if (
            not user.reset_token_expires_at
            or user.reset_token_expires_at <= datetime.now(UTC)
        ):
            raise InvalidTokenError("Password reset token has expired")

        hashed = await asyncio.to_thread(hash_password, new_password)
        await self.user_service.repo.update(
            user.id,
            hashed_password=hashed,
            reset_password_token=None,
            reset_token_expires_at=None,
        )
        await self.auth_repo.invalidate_sessions(user.id)

        await self.audit_service.log_action(
            action="PASSWORD_RESET_SUCCESS",
            resource_type="User",
            resource_id=user.id,
            user_id=user.id,
        )

    async def verify_email(self, token: str) -> None:
        """Verify user email via token."""
        user = await self.user_service.repo.get_by_verification_token(token)
        if (
            not user
            or not user.verification_token_expires_at
            or user.verification_token_expires_at <= datetime.now(UTC)
        ):
            raise InvalidTokenError("Invalid verification token")

        await self.user_service.repo.update(
            user.id,
            is_verified=True,
            verification_token=None,
            verification_token_expires_at=None,
        )

        await self.audit_service.log_action(
            action="EMAIL_VERIFIED",
            resource_type="User",
            resource_id=user.id,
            user_id=user.id,
        )

    async def resend_verification(self, email: str) -> None:
        """Generate and resend email verification token via Celery."""
        user = await self.user_service.repo.get_by_email(email)
        if not user:
            return
        if user.is_verified:
            return

        token = secrets.token_urlsafe(32)
        await self.user_service.repo.update(
            user.id,
            verification_token=hash_refresh_token(token),
            verification_token_expires_at=datetime.now(UTC) + timedelta(days=1),
        )

        from app.worker.tasks import send_verification_email

        ctx = structlog.contextvars.get_contextvars()

        async def enqueue() -> None:
            await asyncio.to_thread(
                send_verification_email.apply_async,
                args=(user.id, token),
                kwargs={"correlation_id": ctx.get("correlation_id")},
                argsrepr="(<account>, <redacted>)",
                expires=86400,
            )

        after_commit(self.db, enqueue)

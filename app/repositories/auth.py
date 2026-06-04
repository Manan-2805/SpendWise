from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import OAuthAccount, RefreshToken


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_refresh_token(
        self,
        user_id: int,
        jti: str,
        family_id: str,
        token_hash: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
        rotated_from_id: int | None = None,
    ) -> RefreshToken:
        """Create and store a new refresh token."""
        token = RefreshToken(
            user_id=user_id,
            jti=jti,
            family_id=family_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            rotated_from_id=rotated_from_id,
        )
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        return token

    async def get_by_jti(self, jti: str) -> RefreshToken | None:
        """Get a refresh token by its JTI."""
        stmt = select(RefreshToken).where(RefreshToken.jti == jti)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Get a refresh token by its hash."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_token(self, jti: str) -> None:
        """Revoke a specific refresh token by setting revoked_at."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.jti == jti, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.session.execute(stmt)

    async def revoke_family(self, family_id: str) -> None:
        """Revoke all tokens in a family."""
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await self.session.execute(stmt)

    async def revoke_all_for_user(self, user_id: int) -> None:
        """Delete all refresh tokens for a user (on logout or password change)."""
        stmt = delete(RefreshToken).where(RefreshToken.user_id == user_id)
        await self.session.execute(stmt)

    async def cleanup_expired(self) -> int:
        """Delete all expired or revoked refresh tokens. Returns count of deleted rows."""
        stmt = delete(RefreshToken).where(
            (RefreshToken.expires_at < datetime.now(UTC))
            | (RefreshToken.revoked_at.is_not(None))
        )
        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def get_oauth_account(
        self, provider: str, provider_account_id: str
    ) -> OAuthAccount | None:
        """Get an OAuth account by provider and provider_account_id."""
        stmt = select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_account_id == provider_account_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_oauth_account(
        self,
        user_id: int,
        provider: str,
        provider_account_id: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
        expires_at: int | None = None,
    ) -> OAuthAccount:
        """Create and link a new OAuth account to a user."""
        account = OAuthAccount(
            user_id=user_id,
            provider=provider,
            provider_account_id=provider_account_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        self.session.add(account)
        await self.session.flush()
        await self.session.refresh(account)
        return account

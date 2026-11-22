"""Normalize identities and add session and lookup constraints."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8b7e2d1c690"
down_revision: str = "0c96d310a672"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("verification_token_expires_at", sa.DateTime(timezone=True)),
    )
    op.execute("UPDATE users SET email = lower(email), username = lower(username)")
    op.execute(
        """
        UPDATE users
        SET verification_token = encode(sha256(convert_to(verification_token, 'UTF8')), 'hex'),
            verification_token_expires_at = now() + interval '1 day'
        WHERE verification_token IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE users
        SET reset_password_token = encode(sha256(convert_to(reset_password_token, 'UTF8')), 'hex')
        WHERE reset_password_token IS NOT NULL
        """
    )
    op.create_index(
        "ix_users_verification_token", "users", ["verification_token"], unique=True
    )
    op.create_index(
        "ix_users_reset_password_token", "users", ["reset_password_token"], unique=True
    )
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.create_index(
        "ix_transactions_active_user_date_id",
        "transactions",
        ["user_id", "transaction_date", "id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_constraint("uq_category_user_name", "categories", type_="unique")
    op.create_index(
        "uq_categories_active_owner_name",
        "categories",
        ["user_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_categories_active_system_name",
        "categories",
        [sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND is_system AND user_id IS NULL"
        ),
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_category_user_name", "categories", ["user_id", "name"]
    )
    op.drop_index("uq_categories_active_system_name", table_name="categories")
    op.drop_index("uq_categories_active_owner_name", table_name="categories")
    op.drop_index("ix_transactions_active_user_date_id", table_name="transactions")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_users_reset_password_token", table_name="users")
    op.drop_index("ix_users_verification_token", table_name="users")
    # Digests cannot be converted back to raw tokens.
    op.execute(
        "UPDATE users SET verification_token = NULL, reset_password_token = NULL"
    )
    op.drop_column("users", "verification_token_expires_at")
    op.drop_column("users", "auth_version")

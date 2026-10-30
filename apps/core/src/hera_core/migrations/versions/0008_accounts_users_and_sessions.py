"""accounts: users, passwords, sessions and one-time tokens

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-29 19:30:00.000000

``core_accounts`` was a record and not a login: one row, keyed by the single owner's id. It folds
into ``account_users`` with that id kept as the user's own, and as an admin, so every row the
install already has belongs to whoever claims it (ADR 27). The row has no password, so the
instance still reads as unclaimed and the setup wizard is what it shows.
"""

from __future__ import annotations

from collections.abc import Sequence

# Autogenerate writes column types out fully qualified but does not import them, so the two this
# project defines are imported here whether or not this particular revision needs them. F401 is
# switched off for this directory in pyproject.toml for exactly that reason.
import hera_storage.base
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False),
        sa.Column("avatar_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_users")),
        sa.UniqueConstraint("email", name=op.f("uq_account_users_email")),
    )
    with op.batch_alter_table("account_users", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_account_users_created_at"), ["created_at", "id"], unique=False
        )

    op.create_table(
        "account_passwords",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_passwords")),
        sa.UniqueConstraint("user_id", name=op.f("uq_account_passwords_user_id")),
    )
    with op.batch_alter_table("account_passwords", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_account_passwords_user_id"), ["user_id"], unique=False)

    op.create_table(
        "account_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("expires_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_account_sessions_token_hash")),
    )
    with op.batch_alter_table("account_sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_account_sessions_user_id"), ["user_id"], unique=False)

    op.create_table(
        "account_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("purpose", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("used_at", hera_storage.base.UTCDateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_account_tokens_token_hash")),
    )
    with op.batch_alter_table("account_tokens", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_account_tokens_user_id"), ["user_id"], unique=False)

    # The owner's record becomes the first user, under the owner's own id -- which is the id
    # every chat, project and profile already carries. Lowercased, because sign-in is.
    op.execute(
        "INSERT INTO account_users"
        " (id, created_at, updated_at, email, name, role, disabled, avatar_type)"
        " SELECT owner_id, created_at, updated_at, lower(trim(email)), name, 'admin', 0,"
        " avatar_type FROM core_accounts"
    )

    with op.batch_alter_table("core_accounts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_core_accounts_created_at"))
        batch_op.drop_index(batch_op.f("ix_core_accounts_owner_id"))
    op.drop_table("core_accounts")


def downgrade() -> None:
    op.create_table(
        "core_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("avatar_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_core_accounts")),
        sa.UniqueConstraint("owner_id", name=op.f("uq_core_accounts_owner_id")),
    )
    with op.batch_alter_table("core_accounts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_core_accounts_created_at"), ["created_at", "id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_core_accounts_owner_id"), ["owner_id"], unique=False)

    # Only the first admin goes back: a single-user schema has room for one person, and the
    # oldest admin is the one who took the owner's id.
    op.execute(
        "INSERT INTO core_accounts (id, created_at, updated_at, owner_id, name, email, avatar_type)"
        " SELECT id, created_at, updated_at, id, name, email, avatar_type FROM account_users"
        " WHERE role = 'admin' ORDER BY created_at LIMIT 1"
    )

    for table in ("account_tokens", "account_sessions", "account_passwords"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(f"ix_{table}_user_id"))
        op.drop_table(table)
    with op.batch_alter_table("account_users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_account_users_created_at"))
    op.drop_table("account_users")

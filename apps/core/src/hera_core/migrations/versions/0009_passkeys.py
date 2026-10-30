"""accounts: passkeys

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-30 18:00:00.000000

A person's WebAuthn credentials (ADR 27, M4): the public half of each key, its credential id and
its signature counter. Nothing to carry over — there were no passkeys before this.
"""

from __future__ import annotations

from collections.abc import Sequence

import hera_storage.base
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_passkeys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("public_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False),
        sa.Column("transports", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("last_used_at", hera_storage.base.UTCDateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_passkeys")),
        sa.UniqueConstraint("credential_id", name=op.f("uq_account_passkeys_credential_id")),
    )
    with op.batch_alter_table("account_passkeys", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_account_passkeys_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("account_passkeys", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_account_passkeys_user_id"))
    op.drop_table("account_passkeys")

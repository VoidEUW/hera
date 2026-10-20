"""an account for the owner

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-03 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import hera_storage.base
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    with op.batch_alter_table("core_accounts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_core_accounts_owner_id"))
        batch_op.drop_index(batch_op.f("ix_core_accounts_created_at"))

    op.drop_table("core_accounts")

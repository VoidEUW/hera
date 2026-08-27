"""skills pinned to a chat

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-27 20:35:00.000000
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

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable, and left null on existing rows: an empty list and "never chosen any" are the
    # same thing to read, and backfilling every chat with `[]` would write to every row to say
    # nothing.
    with op.batch_alter_table("chat_chats", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pinned_skills", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_chats", schema=None) as batch_op:
        batch_op.drop_column("pinned_skills")

"""projects you can organise by

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-28 11:20:00.000000
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

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Both nullable and both left null on existing rows, for the reason 0003 gives: "never set"
    # and the default are the same thing to read, and backfilling every row to say nothing is a
    # write that can only go wrong.
    #
    # `default_agent_id` is a seam — nothing reads it in v0.2. It is added now because the shape
    # is already known and a migration later would cost the same and buy nothing.
    with op.batch_alter_table("chat_projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("default_agent_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("color", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_projects", schema=None) as batch_op:
        batch_op.drop_column("color")
        batch_op.drop_column("default_agent_id")

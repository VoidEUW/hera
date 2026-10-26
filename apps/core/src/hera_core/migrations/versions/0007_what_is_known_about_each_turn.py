"""what is known about each turn

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-26 18:00:00.000000

Its own revision, not an edit of 0006: a database that already ran 0006 is at 0006 and will
never run it again, so columns added to it afterwards would simply be missing there -- which is
what happened, and every read of the ledger failed on a column that did not exist.
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

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_usage", schema=None) as batch_op:
        # Every row so far is a turn: the title request was not counted before this.
        batch_op.add_column(
            sa.Column(
                "source",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="turn",
            )
        )
        # Unknown on every existing row, not nought: nothing read these before (ADR 25).
        batch_op.add_column(sa.Column("cached_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reasoning_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("first_token_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("generating_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("timed_completion_tokens", sa.Integer(), nullable=True))

    # The default was only for the rows already there; the model writes `source` itself.
    with op.batch_alter_table("chat_usage", schema=None) as batch_op:
        batch_op.alter_column("source", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("chat_usage", schema=None) as batch_op:
        batch_op.drop_column("timed_completion_tokens")
        batch_op.drop_column("generating_ms")
        batch_op.drop_column("first_token_ms")
        batch_op.drop_column("reasoning_tokens")
        batch_op.drop_column("cached_tokens")
        batch_op.drop_column("source")

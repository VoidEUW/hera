"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
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

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}

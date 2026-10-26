"""what each turn cost

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-26 12:00:00.000000
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Any

# Autogenerate writes column types out fully qualified but does not import them, so the two this
# project defines are imported here whether or not this particular revision needs them. F401 is
# switched off for this directory in pyproject.toml for exactly that reason.
import hera_storage.base
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAMP = hera_storage.base.UTCDateTime(timezone=True)

# Described here rather than imported from `hera_chats`: a migration is a fixed point in the
# schema's history, and the model it would import keeps moving after it.
_messages = sa.table(
    "chat_messages",
    sa.column("id", sa.Uuid()),
    sa.column("owner_id", sa.Uuid()),
    sa.column("chat_id", sa.Uuid()),
    sa.column("role", sa.String()),
    sa.column("events", sa.JSON()),
    sa.column("updated_at", _STAMP),
)
_usage = sa.table(
    "chat_usage",
    sa.column("id", sa.Uuid()),
    sa.column("created_at", _STAMP),
    sa.column("updated_at", _STAMP),
    sa.column("owner_id", sa.Uuid()),
    sa.column("chat_id", sa.Uuid()),
    sa.column("message_id", sa.Uuid()),
    sa.column("ordinal", sa.Integer()),
    sa.column("at", _STAMP),
    sa.column("prompt_tokens", sa.Integer()),
    sa.column("completion_tokens", sa.Integer()),
)


def upgrade() -> None:
    op.create_table(
        "chat_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("at", hera_storage.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_usage")),
        sa.UniqueConstraint("message_id", "ordinal", name=op.f("uq_chat_usage_message_id")),
    )
    with op.batch_alter_table("chat_usage", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_chat_usage_created_at"), ["created_at", "id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_chat_usage_owner_id"), ["owner_id", "at"], unique=False
        )

    # What was spent before there was a ledger is still in the messages that remain. Dated by
    # when each message was last written, which for a finished turn is when it closed.
    rows = list(_backfill(op.get_bind()))
    if rows:
        op.bulk_insert(_usage, rows)


def downgrade() -> None:
    with op.batch_alter_table("chat_usage", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chat_usage_owner_id"))
        batch_op.drop_index(batch_op.f("ix_chat_usage_created_at"))

    op.drop_table("chat_usage")


def _backfill(connection: sa.Connection) -> Iterator[dict[str, Any]]:
    found = connection.execute(
        sa.select(
            _messages.c.id,
            _messages.c.owner_id,
            _messages.c.chat_id,
            _messages.c.events,
            _messages.c.updated_at,
        ).where(_messages.c.role == "assistant")
    )
    for message_id, owner_id, chat_id, events, updated_at in found:
        closes = [
            event
            for event in events or []
            if isinstance(event, dict) and event.get("type") == "turn_closed"
        ]
        for ordinal, close in enumerate(closes):
            usage = close.get("usage")
            if not isinstance(usage, dict):
                continue
            yield _row(owner_id, chat_id, message_id, ordinal, updated_at, usage)


def _row(
    owner_id: uuid.UUID,
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
    ordinal: int,
    at: datetime,
    usage: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "created_at": at,
        "updated_at": at,
        "owner_id": owner_id,
        "chat_id": chat_id,
        "message_id": message_id,
        "ordinal": ordinal,
        "at": at,
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
    }

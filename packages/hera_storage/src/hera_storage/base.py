"""Reusable model mixins and the shared metadata configuration.

Nothing in this module is a table. All three mixins are plain ``SQLModel`` classes
without ``table=True``; downstream libraries combine them into their own models::

    class Recipe(Entity, SoftDeletable, Versioned, table=True):
        __tablename__ = "cook_recipes"
        title: str
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Dialect, Index, TypeDecorator
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import declared_attr
from sqlmodel import Field, SQLModel

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
"""Standard SQLAlchemy naming convention for indexes and constraints.

Applied to ``SQLModel.metadata`` at import time, which is why importing ``hera_storage``
before defining any table matters: a convention only affects constraints created after
it was set. Without deterministic names, Alembic's batch mode -- the only way to alter a
column under SQLite -- fails on unnamed constraints.
"""

SQLModel.metadata.naming_convention = NAMING_CONVENTION


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class EntityStatus(StrEnum):
    """Lifecycle state of a soft-deletable row."""

    ACTIVE = "active"
    REVOKED = "revoked"


# Both column types are annotated ``Any`` because SQLModel's ``sa_type`` is typed as
# ``type[Any]``, although instances -- the only way to pass options like timezone=True or
# to use a TypeDecorator -- are what it actually expects.
_STATUS_TYPE: Any = SAEnum(EntityStatus, native_enum=False, name="entitystatus")
"""Plain ``VARCHAR`` on both SQLite and PostgreSQL, converted back to
:class:`EntityStatus` when loaded.

Deliberately not a native PostgreSQL enum: those need their own migration step for every
value added, and the two backends would then produce different DDL. No CHECK constraint
either -- SQLAlchemy leaves ``create_constraint=False`` by default, which keeps Alembic's
batch mode under SQLite simple.
"""


def _to_utc(value: datetime | None) -> datetime | None:
    """Normalise a datetime to aware UTC. ``None`` passes through.

    A naive value is taken to be UTC rather than local time -- guessing the machine's
    timezone would make the same data mean different things on two machines.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """A ``DateTime`` that is always timezone-aware UTC in Python, on every backend.

    SQLite stores no offset, so a plain ``DateTime(timezone=True)`` hands back naive values
    from SQLite while PostgreSQL returns aware ones -- and code that subtracts one from
    ``datetime.now(UTC)`` then fails on one backend only. This normalises both directions
    instead: anything written is converted to UTC, anything read comes back aware in UTC.

    The DDL is unchanged (SQLite ``DATETIME``, PostgreSQL ``TIMESTAMP WITH TIME ZONE``), so
    adopting it is not a schema change. Use it for your own timestamp columns too.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return _to_utc(value)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return _to_utc(value)


_TIMESTAMP_TYPE: Any = UTCDateTime()


class Entity(SQLModel):
    """Identity and audit timestamps: ``id``, ``created_at``, ``updated_at``."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_type=_TIMESTAMP_TYPE,
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=_TIMESTAMP_TYPE,
        nullable=False,
        # Fires inside the UPDATE statement, so plain attribute assignment is enough --
        # no repository code ever has to touch this field.
        sa_column_kwargs={"onupdate": utcnow},
    )

    # `.directive`, not plain declared_attr: __table_args__ is a declarative directive,
    # not a mapped attribute.
    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:
        """Covers the default ordering of :meth:`hera_storage.Repository.list`.

        A ``declared_attr`` so every table gets its own Index object -- one instance cannot
        be shared. Caveat: a model that declares its own ``__table_args__`` shadows this
        one and silently loses the index. Such a model should include
        ``Index(None, "created_at", "id")`` itself.
        """
        return (Index(None, "created_at", "id"),)


class SoftDeletable(SQLModel):
    """Revocation instead of deletion: rows stay, queries filter them out by default."""

    # Indexed because every default query filters on it.
    status: EntityStatus = Field(
        default=EntityStatus.ACTIVE, sa_type=_STATUS_TYPE, nullable=False, index=True
    )
    revoked_at: datetime | None = Field(default=None, sa_type=_TIMESTAMP_TYPE, nullable=True)


class Versioned(SQLModel):
    """Snapshot versioning: every version is its own row, linked backwards in a chain."""

    version: int = Field(default=1, nullable=False)
    supersedes_id: UUID | None = Field(default=None)
    """Id of the previous version. Intentionally a bare UUID without a foreign key."""

    origin: str | None = Field(default=None)
    """Free-form provenance marker, e.g. ``"manual"``, ``"dream:<uuid>"``, ``"selection:gen7"``."""

    is_current: bool = Field(default=True, nullable=False, index=True)

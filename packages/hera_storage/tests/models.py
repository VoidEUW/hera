"""Dummy models for the test suite.

There is nothing domain-specific in this library to test, so the tests bring their own
throwaway models. They all live in this one module because every model registers into the
shared ``SQLModel.metadata`` -- declaring the same table twice would collide.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from hera_storage import Entity, SoftDeletable, Versioned


class Widget(Entity, SoftDeletable, Versioned, table=True):
    """All three mixins combined, exactly as a domain library would."""

    __tablename__ = "test_widgets"

    name: str
    size: int = 0


class Gizmo(Entity, SoftDeletable, Versioned, table=True):
    """A second class over the same mixins, proving no column object is shared."""

    __tablename__ = "test_gizmos"

    label: str


class Gadget(Entity, table=True):
    """Not soft-deletable: ``include_revoked`` must be ignored, ``revoke`` must raise."""

    __tablename__ = "test_gadgets"

    name: str


class Doodad(Entity, table=True):
    """Carries a unique column and an index, for the Conflict and naming tests."""

    __tablename__ = "test_doodads"

    code: str = Field(unique=True)
    bucket: str = Field(default="", index=True)


class Trinket(SQLModel, table=True):
    """Not an Entity at all: no created_at, so no default ordering to apply."""

    __tablename__ = "test_trinkets"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str

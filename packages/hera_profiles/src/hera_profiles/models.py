"""The profile table: one row per version of her.

A **profile** is what the composer's dropdown selects. It is not a model picker — there is one
model (ADR 2) — and it is not a project. ``docs/frontend.md`` draws the line: a profile answers
*who she is* and a project answers *what we are working on*, and the two compose.

A profile owns no text. Every word it contributes comes from a mind region in the git
repository; the row says which regions are switched off, what a region says *instead* for this
profile, and which traits are set. That keeps one copy of her character on disk and makes
"coding Hera" a small diff against "Hera" rather than a second full mind.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field

from hera_prompts import TraitValue
from hera_storage import Entity, SoftDeletable

DEFAULT_SLUG = "hera"
"""The profile every install starts with, and the one a chat falls back to."""

JSON_FIELDS: tuple[str, ...] = ("disabled_regions", "overrides", "traits", "pinned_skills")
"""The columns SQLAlchemy cannot notice a change to on its own.

A JSON column holds a dict or a list, and SQLAlchemy detects a change by comparing the
attribute to its loaded value -- which is the *same object* after an in-place edit. So
``profile.overrides["approach"] = ...`` issues no UPDATE and is lost at the next restart.

``sqlalchemy.ext.mutable`` exists for exactly this and does not work here: SQLModel's
``__setattr__`` calls SQLAlchemy's ``set_attribute`` first and then writes the *raw* value into
the model's ``__dict__``, so the coerced ``MutableDict`` is overwritten the moment it is
created. Rather than a wrapper that silently does nothing,
:class:`~hera_profiles.repository.ProfileRepository` flags these four by name on save.
"""

# SQLModel's `sa_column` parameter is typed `type[Any]` although an instance is what it wants.
_JSON: Any = JSON


class Profile(Entity, SoftDeletable, table=True):
    """One of her.

    Soft-deletable rather than deletable: a chat records which profile answered it, as a bare
    UUID with no foreign key behind it, and a hard delete would turn that into a dangling
    reference nobody can explain later.
    """

    __tablename__ = "profile_profiles"

    # Entity declares __table_args__ through a `declared_attr`, and a class-level one shadows
    # it -- so the default-ordering index has to be repeated here by hand. See
    # hera_storage.base.Entity.__table_args__.
    __table_args__ = (
        UniqueConstraint("owner_id", "slug"),
        Index(None, "created_at", "id"),
    )

    owner_id: UUID = Field(index=True)
    """Whose profile this is. Single-user in v0.1, behind a multi-user-ready seam: every row
    carries an owner and every route resolves one, so turning the seam on is a login screen
    rather than a migration."""

    slug: str
    """Stable, URL-safe handle. Unique per owner."""

    name: str
    """What the dropdown shows."""

    description: str = ""

    is_default: bool = Field(default=False, index=True)
    """Whether a new chat outside any project starts here. At most one per owner, which
    :class:`~hera_profiles.repository.ProfileRepository` enforces rather than the schema —
    a partial unique index is not portable between SQLite and PostgreSQL."""

    disabled_regions: list[str] = Field(default_factory=list, sa_column=Column(_JSON))
    """Region ids this profile leaves out of the prompt entirely."""

    overrides: dict[str, str] = Field(default_factory=dict, sa_column=Column(_JSON))
    """Region id → the text this profile uses instead of what the file says.

    The escape hatch that makes profiles cheap. A coding profile that wants a different
    ``approach`` overrides that one region and inherits the other eleven, so a change to her
    character reaches every profile at once. An override is deliberately *not* versioned in
    git: it belongs to this profile, not to the mind.
    """

    traits: dict[str, TraitValue] = Field(default_factory=dict, sa_column=Column(_JSON))
    """Behaviour traits, validated against :data:`hera_profiles.traits.BEHAVIOUR_TRAITS`."""

    pinned_skills: list[str] = Field(default_factory=list, sa_column=Column(_JSON))
    """Skill names always given to her under this profile.

    Bare strings, never a foreign key: ``hera_profiles`` sits below ``hera_skillsets`` and may
    not import it. The router resolves the names and reports the ones that no longer exist.
    """

    renderer_format: str = "xml"
    """How the prompt is laid out: ``xml``, ``keyvalue`` or ``markdown``.

    XML by default because ADR 2 targets a model with enough capacity for tagged structure,
    and because a tag says where a section ends — which matters most for the sections whose
    content came from somewhere else.
    """

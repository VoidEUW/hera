"""What a skill is, what is wrong with the ones that are broken, and how often each is used."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field as SQLField

from hera_storage import Entity, UTCDateTime

# SQLModel's `sa_type` is annotated `type[Any]` although an instance is what it wants.
_TIMESTAMP: Any = UTCDateTime()

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
"""What a skill directory may be called.

Lowercase, digits and hyphens. The id ends up in a ``/slash`` command and in a URL, and the
same character set is what Claude Code accepts — skills are portable in both directions
(ADR 5), so this is not ours to widen.
"""

SKILL_FILENAME = "SKILL.md"


class Skill(BaseModel):
    """One ``SKILL.md`` package on disk.

    Not a table. A skill is content in a directory, syncable from a git repository and
    readable by Claude Code pointed at the same folder; giving it a row would create a second
    place that has an opinion about which skills exist.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    """The **directory name**, and the canonical identifier.

    Not the frontmatter ``name``. The directory is what a person sees, what ``/slash``
    addresses, and what survives someone editing the file's first lines; a frontmatter name
    that disagrees is reported in :attr:`problems` rather than honoured, because two sources of
    truth for an identifier is how a skill becomes unreachable by the name it appears under.
    """

    name: str
    """The frontmatter ``name``, for display. Falls back to :attr:`id`."""

    description: str
    """The frontmatter ``description``.

    The most important line in a ``SKILL.md``: ADR 5 retrieves on it, so a skill whose
    description does not say *when to use this* will never be selected by retrieval, however
    good its body is.
    """

    body: str
    """Everything after the frontmatter. Injected in full when the skill is selected."""

    path: Path
    """The directory, so the settings screen can offer to open it."""

    resources: tuple[str, ...] = ()
    """Other files beside ``SKILL.md``, relative to the directory.

    Named but not read. A skill's body refers to these for progressive disclosure inside the
    skill itself; reaching them is a filesystem tool's job, not this package's.
    """

    metadata: dict[str, str] = Field(default_factory=dict)
    """Frontmatter keys this package does not interpret — ``author``, ``license`` and so on."""

    digest: str = ""
    """SHA-256 of the ``SKILL.md`` that produced this, hex.

    Content, not provenance: this package says *what the file is*, and whoever holds a list of
    digests they trust says whether that is one of them. Two reasons it is computed here rather
    than by the thing doing the trusting — the bytes are already in hand, and a second reader
    would be a second opinion about which bytes count.

    Taken over the decoded text, so a file checked out with CRLF endings hashes the same as the
    one it was signed from. The body alone would be the wrong thing to hash: a skill's
    frontmatter is what decides when it fires.
    """

    problems: tuple[str, ...] = ()
    """What is wrong with this skill, in sentences for a person to read.

    A skill with problems still loads and can still be used. Refusing to load it would hide
    the thing that needs fixing behind an absence.
    """

    @property
    def usable(self) -> bool:
        """Whether this skill has enough to be worth injecting."""
        return bool(self.body.strip())


class BrokenSkill(BaseModel):
    """A directory that looked like a skill and could not be loaded at all."""

    model_config = ConfigDict(frozen=True)

    id: str
    path: Path
    reason: str


class SkillUsage(Entity, table=True):
    """How often one owner has actually been given one skill.

    Exists for the settings screen, which sorts by last used — and for the only feedback loop
    that tells you retrieval is picking the wrong thing. A skill nothing ever selects is
    either badly described or not needed, and both are worth seeing.
    """

    __tablename__ = "skill_usages"

    # Entity supplies this through a declared_attr, and a class-level __table_args__ shadows
    # it. See hera_storage.base.Entity.__table_args__.
    __table_args__ = (
        UniqueConstraint("owner_id", "skill_id"),
        Index(None, "created_at", "id"),
    )

    owner_id: UUID = SQLField(index=True)
    skill_id: str = SQLField(index=True)
    """The directory name. A bare string, not a foreign key — a skill is a folder, and it can
    be deleted from under this row without the database knowing."""

    hits: int = 0
    last_used_at: datetime | None = SQLField(default=None, sa_type=_TIMESTAMP)

"""Every skill installed, and the ones that would not load.

``$HERA_HOME/skills`` holds one directory per skill. It is content, not configuration: a git
clone, a sparse checkout, or a symlink to whatever Claude Code already reads. Nothing here
writes to it — syncing is somebody else's job, and a package that both reads and rewrites the
folder you point it at is a package you cannot safely point at your own.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from hera_home import skills_dir
from hera_skillsets.errors import UnknownSkill
from hera_skillsets.loader import load_skill
from hera_skillsets.models import SKILL_FILENAME, BrokenSkill, Skill


class Catalogue(BaseModel):
    """One scan of the skills directory."""

    model_config = ConfigDict(frozen=True)

    skills: tuple[Skill, ...] = ()
    broken: tuple[BrokenSkill, ...] = ()
    """Directories that looked like skills and could not be read. Surfaced rather than
    skipped: a skill that vanished silently is indistinguishable from one never installed."""

    def get(self, skill_id: str) -> Skill | None:
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        return None

    def ids(self) -> list[str]:
        return [skill.id for skill in self.skills]

    def __contains__(self, skill_id: object) -> bool:
        return isinstance(skill_id, str) and self.get(skill_id) is not None

    def __len__(self) -> int:
        return len(self.skills)


class SkillLibrary:
    """The skills on disk, re-read when they change.

    Cheap to ask twice. A scan stats every ``SKILL.md`` and re-reads only if one of them moved
    — a directory of thirty skills costs thirty stat calls, which is nothing next to a model
    round trip, and it means editing a skill in an editor takes effect on the next turn with
    nothing to restart.
    """

    def __init__(self, path: Path | None = None, *, ttl_s: float = 0.0) -> None:
        self.path = path if path is not None else skills_dir()
        # Seconds to trust a scan without re-stating the directory. Zero checks mtimes on
        # every call, which is right for a local disk; raise it only if the skills directory
        # turns out to live on something slow, like a network mount.
        self.ttl_s = ttl_s
        self._catalogue = Catalogue()
        self._signature: tuple[tuple[str, float], ...] | None = None
        self._checked_at = 0.0

    def catalogue(self) -> Catalogue:
        """Every skill, re-scanned if anything on disk changed."""
        now = time.monotonic()
        if self._signature is not None and now - self._checked_at < self.ttl_s:
            return self._catalogue
        self._checked_at = now
        signature = self._signature_of_disk()
        if signature != self._signature:
            self._signature = signature
            self._catalogue = self._scan()
        return self._catalogue

    def get(self, skill_id: str) -> Skill | None:
        """One skill, or ``None``."""
        return self.catalogue().get(skill_id)

    def require(self, skill_id: str) -> Skill:
        """One skill, or :class:`~hera_skillsets.errors.UnknownSkill`."""
        found = self.get(skill_id)
        if found is None:
            raise UnknownSkill(skill_id, self.catalogue().ids())
        return found

    def ids(self) -> list[str]:
        return self.catalogue().ids()

    def all(self) -> Sequence[Skill]:
        return self.catalogue().skills

    def resolve(self, names: Sequence[str]) -> tuple[list[Skill], list[str]]:
        """Turn names into skills, keeping the ones that no longer exist apart.

        A profile pins skills by name and a skill is a folder, so the folder can be deleted
        from under it. The caller needs both halves: what she got, and what was asked for and
        is gone — the second is what the settings screen shows as a dangling pin.
        """
        catalogue = self.catalogue()
        found: list[Skill] = []
        missing: list[str] = []
        for name in names:
            skill = catalogue.get(name)
            if skill is None:
                missing.append(name)
            else:
                found.append(skill)
        return found, missing

    def _signature_of_disk(self) -> tuple[tuple[str, float], ...]:
        """Directory names paired with their skill file's mtime.

        Catches an edit, a new skill and a deleted one. It does not catch an edit that leaves
        the mtime untouched, which takes deliberate effort to arrange.
        """
        if not self.path.is_dir():
            return ()
        found: list[tuple[str, float]] = []
        for entry in sorted(self.path.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            source = entry / SKILL_FILENAME
            try:
                mtime = source.stat().st_mtime
            except OSError:
                mtime = -1.0
            found.append((entry.name, mtime))
        return tuple(found)

    def _scan(self) -> Catalogue:
        skills: list[Skill] = []
        broken: list[BrokenSkill] = []
        for name, _ in self._signature_of_disk():
            loaded = load_skill(self.path / name)
            if isinstance(loaded, Skill):
                skills.append(loaded)
            else:
                broken.append(loaded)
        return Catalogue(skills=tuple(skills), broken=tuple(broken))


class SkillLibraryPort:
    """``SkillLibrary`` in the shape ``hera_tools`` wants for ``hera__skill``.

    Shaped to satisfy ``hera_tools.ports.SkillLibrary`` **without importing it**: this package
    sits below the tool layer and may not depend on it, so the protocol is matched
    structurally and the application checks the fit. ``apps/core`` has a test that holds this
    class against the real protocol, which is the only place both may be imported.

    Async because the port is. Nothing here awaits anything — a skill is a small file on local
    disk — but a synchronous port would force every other implementation through a thread.
    """

    def __init__(self, library: SkillLibrary) -> None:
        self.library = library

    async def load(self, name: str) -> str | None:
        skill = self.library.get(name)
        return skill.body if skill is not None else None

    async def names(self) -> Sequence[str]:
        return self.library.ids()

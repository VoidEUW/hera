"""Fixtures for the skillsets suite.

Skills are files, so every test writes real ones into a temporary directory. There is no
in-memory skill: the parsing, the mtime cache and the "directory name wins" rule are all
about what is actually on disk, and a fixture that handed back constructed `Skill` objects
would test none of them.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

# Importing the model registers skill_usages into SQLModel.metadata, which is what the `db`
# fixture from hera_storage creates tables from.
from hera_skillsets.models import SkillUsage  # noqa: F401
from skill_support import WriteSkill
from sqlmodel import Session

from hera_skillsets import SkillLibrary, SkillRouter, SkillUsageRepository


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERA_HOME", str(tmp_path / "home"))


@pytest.fixture
def skills_path(tmp_path: Path) -> Path:
    path = tmp_path / "skills"
    path.mkdir()
    return path


@pytest.fixture
def write_skill(skills_path: Path) -> WriteSkill:
    """Write a skill directory. Returns its path.

    ``frontmatter=None`` writes the file with no fences at all, which is a real thing people
    do and a case the loader has to answer for.
    """

    def write(
        skill_id: str,
        *,
        description: str = "Does a thing.",
        body: str = "Do the thing carefully.",
        name: str | None = None,
        frontmatter: str | None = "",
        extra: dict[str, str] | None = None,
    ) -> Path:
        directory = skills_path / skill_id
        directory.mkdir(parents=True, exist_ok=True)
        if frontmatter is None:
            directory.joinpath("SKILL.md").write_text(body, encoding="utf-8")
            return directory
        lines = [f"name: {name if name is not None else skill_id}"]
        if description:
            lines.append(f"description: {description}")
        if frontmatter:
            lines.append(frontmatter)
        for key, value in (extra or {}).items():
            directory.joinpath(key).write_text(value, encoding="utf-8")
        document = "---\n" + "\n".join(lines) + "\n---\n" + body + "\n"
        directory.joinpath("SKILL.md").write_text(document, encoding="utf-8")
        return directory

    return write


@pytest.fixture
def library(skills_path: Path) -> SkillLibrary:
    return SkillLibrary(skills_path)


@pytest.fixture
def router(library: SkillLibrary) -> SkillRouter:
    return SkillRouter(library)


@pytest.fixture
def owner_id() -> UUID:
    return uuid4()


@pytest.fixture
def usage(session: Session) -> SkillUsageRepository:
    return SkillUsageRepository(session)

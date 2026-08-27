"""The library: scanning, the mtime cache, and resolving names."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from skill_support import WriteSkill

from hera_skillsets import SkillLibrary, SkillLibraryPort, UnknownSkill


def touch(path: Path, *, seconds_later: int = 10) -> None:
    """Move a file's mtime forward. Rewriting alone is not reliable within one clock tick."""
    stamp = path.stat().st_mtime + seconds_later
    os.utime(path, (stamp, stamp))


class TestScanning:
    def test_an_absent_directory_is_empty_rather_than_an_error(self, tmp_path: Path) -> None:
        """A fresh install has no skills, and that is not a failure state."""
        assert SkillLibrary(tmp_path / "nothing-here").ids() == []

    def test_skills_come_back_sorted_by_directory_name(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("writing")
        write_skill("tdd")
        assert library.ids() == ["tdd", "writing"]

    def test_hidden_directories_are_ignored(
        self, library: SkillLibrary, skills_path: Path, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        (skills_path / ".git").mkdir()
        assert library.ids() == ["tdd"]

    def test_loose_files_are_ignored(
        self, library: SkillLibrary, skills_path: Path, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        (skills_path / "README.md").write_text("not a skill")
        assert library.ids() == ["tdd"]

    def test_nothing_is_written_to_the_skills_directory(
        self, library: SkillLibrary, skills_path: Path, write_skill: WriteSkill
    ) -> None:
        """A package that rewrites the folder you point it at is one you cannot safely point
        at your own."""
        write_skill("tdd")
        before = sorted(path.name for path in skills_path.rglob("*"))
        library.catalogue()
        assert sorted(path.name for path in skills_path.rglob("*")) == before


class TestTheCache:
    def test_an_edited_skill_is_picked_up_without_a_restart(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        path = write_skill("tdd", body="First.")
        assert library.require("tdd").body == "First."

        write_skill("tdd", body="Second.")
        touch(path / "SKILL.md")

        assert library.require("tdd").body == "Second."

    def test_a_new_skill_appears(self, library: SkillLibrary, write_skill: WriteSkill) -> None:
        write_skill("tdd")
        assert library.ids() == ["tdd"]

        write_skill("writing")

        assert library.ids() == ["tdd", "writing"]

    def test_a_deleted_skill_disappears(
        self, library: SkillLibrary, skills_path: Path, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        write_skill("writing")
        library.catalogue()

        for path in sorted((skills_path / "writing").rglob("*"), reverse=True):
            path.unlink()
        (skills_path / "writing").rmdir()

        assert library.ids() == ["tdd"]

    def test_an_unchanged_directory_is_not_re_read(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        first = library.catalogue()
        assert library.catalogue() is first

    def test_a_ttl_holds_the_scan_without_stating_anything(
        self, skills_path: Path, write_skill: WriteSkill
    ) -> None:
        """The escape hatch for a skills directory on something slow."""
        path = write_skill("tdd", body="First.")
        library = SkillLibrary(skills_path, ttl_s=3600)
        assert library.require("tdd").body == "First."

        write_skill("tdd", body="Second.")
        touch(path / "SKILL.md")

        assert library.require("tdd").body == "First."


class TestLookup:
    def test_get_returns_none_for_an_unknown_skill(self, library: SkillLibrary) -> None:
        assert library.get("nope") is None

    def test_require_raises_and_names_what_was_available(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        with pytest.raises(UnknownSkill) as caught:
            library.require("tdc")
        assert caught.value.known == ["tdd"]
        assert "tdd" in str(caught.value)

    def test_require_says_so_when_nothing_is_installed(self, library: SkillLibrary) -> None:
        with pytest.raises(UnknownSkill, match="none installed"):
            library.require("tdd")

    def test_resolve_keeps_the_found_and_the_missing_apart(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        """A profile pins by name and a skill is a folder, so the folder can be deleted from
        under the pin. Both halves are needed: what she got, and what is gone."""
        write_skill("tdd")

        found, missing = library.resolve(["tdd", "deleted-last-week"])

        assert [skill.id for skill in found] == ["tdd"]
        assert missing == ["deleted-last-week"]

    def test_membership_and_length_read_naturally(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        catalogue = library.catalogue()
        assert "tdd" in catalogue
        assert 42 not in catalogue
        assert len(catalogue) == 1


class TestThePort:
    """The shape hera_tools' `hera__skill` needs, matched structurally rather than by import:
    this package sits below the tool layer. apps/core holds it against the real protocol."""

    async def test_load_returns_the_body(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd", body="Red, green, refactor.")
        assert await SkillLibraryPort(library).load("tdd") == "Red, green, refactor."

    async def test_load_returns_none_for_an_unknown_skill(self, library: SkillLibrary) -> None:
        """The port's contract: None, so the tool can tell the model what it could have
        asked for instead of raising into the turn."""
        assert await SkillLibraryPort(library).load("nope") is None

    async def test_names_lists_everything(
        self, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        write_skill("writing")
        assert list(await SkillLibraryPort(library).names()) == ["tdd", "writing"]


class TestDefaultLocation:
    def test_the_path_follows_hera_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("HERA_HOME", str(tmp_path / "elsewhere"))
        assert SkillLibrary().path == tmp_path / "elsewhere" / "skills"

"""Reading SKILL.md, and reporting what is wrong with the ones that are broken.

The theme throughout: bad content produces a listed problem, never an exception. A Hera that
refuses to boot over a stray colon in someone's YAML is worse than one skill marked broken.
"""

from __future__ import annotations

from pathlib import Path

from hera_skillsets.loader import MAX_DESCRIPTION
from skill_support import WriteSkill

from hera_skillsets import BrokenSkill, Skill, SkillLibrary, load_skill


def loaded(path: Path) -> Skill:
    skill = load_skill(path)
    assert isinstance(skill, Skill), skill
    return skill


class TestAWellFormedSkill:
    def test_it_reads_frontmatter_and_body(self, write_skill: WriteSkill) -> None:
        skill = loaded(write_skill("tdd", description="Test first.", body="# TDD\nRed, green."))

        assert skill.id == "tdd"
        assert skill.name == "tdd"
        assert skill.description == "Test first."
        assert skill.body == "# TDD\nRed, green."
        assert skill.problems == ()

    def test_unknown_frontmatter_keys_are_kept_not_dropped(self, write_skill: WriteSkill) -> None:
        """The format is Claude Code's and it is not ours to narrow."""
        skill = loaded(write_skill("tdd", frontmatter="author: Lukas Kreuz\nlicense: MIT"))
        assert skill.metadata == {"author": "Lukas Kreuz", "license": "MIT"}

    def test_a_description_with_a_colon_survives(self, write_skill: WriteSkill) -> None:
        """`description: Use when: you need X` is a natural sentence and invalid YAML -- a
        plain scalar may not contain ": " -- and PyYAML rejects the whole block over it.
        Without the line-by-line rescue the skill silently becomes unretrievable and nothing
        says why."""
        skill = loaded(write_skill("tdd", description="Use when: you want tests first."))

        assert skill.description == "Use when: you want tests first."
        assert any("read line by line" in p for p in skill.problems)

    def test_neighbouring_files_are_named_but_not_read(self, write_skill: WriteSkill) -> None:
        path = write_skill("tdd", extra={"mocking.md": "x" * 10_000})
        (path / "references").mkdir()

        skill = loaded(path)

        assert skill.resources == ("mocking.md", "references/")
        assert "x" * 10_000 not in skill.body

    def test_hidden_files_are_not_resources(self, write_skill: WriteSkill) -> None:
        path = write_skill("tdd", extra={".DS_Store": ""})
        assert loaded(path).resources == ()


class TestTheIdentifier:
    def test_the_directory_name_wins_over_the_frontmatter(self, write_skill: WriteSkill) -> None:
        """Two sources of truth for an identifier is how a skill becomes unreachable under
        the name it appears with."""
        skill = loaded(write_skill("tdd", name="test-driven-development"))

        assert skill.id == "tdd"
        assert skill.name == "test-driven-development"
        assert any("directory wins" in problem for problem in skill.problems)

    def test_a_missing_name_falls_back_to_the_directory(self, write_skill: WriteSkill) -> None:
        skill = loaded(write_skill("tdd", name=""))
        assert skill.name == "tdd"
        assert skill.problems == ()

    def test_an_unusable_directory_name_is_reported(self, skills_path: Path) -> None:
        directory = skills_path / "Test Driven"
        directory.mkdir()
        (directory / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\nbody\n")

        skill = loaded(directory)

        assert any("not a usable directory name" in problem for problem in skill.problems)


class TestProblems:
    def test_no_description_says_what_that_costs(self, write_skill: WriteSkill) -> None:
        skill = loaded(write_skill("tdd", description=""))
        assert any("retrieval can never select it" in p for p in skill.problems)

    def test_an_essay_of_a_description_is_reported(self, write_skill: WriteSkill) -> None:
        """A description that matches everything is the same as one that matches nothing."""
        skill = loaded(write_skill("tdd", description="x " * MAX_DESCRIPTION))
        assert any("matches everything" in p for p in skill.problems)

    def test_an_empty_body_is_reported_and_the_skill_is_unusable(
        self, write_skill: WriteSkill
    ) -> None:
        skill = loaded(write_skill("tdd", body=""))
        assert any("nothing to inject" in p for p in skill.problems)
        assert not skill.usable

    def test_no_frontmatter_at_all_still_loads(self, write_skill: WriteSkill) -> None:
        skill = loaded(write_skill("tdd", frontmatter=None, body="Just prose."))
        assert skill.body == "Just prose."
        assert any("no YAML frontmatter" in p for p in skill.problems)

    def test_an_unclosed_fence_is_reported(self, skills_path: Path) -> None:
        directory = skills_path / "tdd"
        directory.mkdir()
        (directory / "SKILL.md").write_text("---\nname: tdd\ndescription: x\nbody with no fence")

        skill = loaded(directory)

        assert any("never closed" in p for p in skill.problems)

    def test_invalid_yaml_is_reported_with_the_parser_error(self, skills_path: Path) -> None:
        directory = skills_path / "tdd"
        directory.mkdir()
        (directory / "SKILL.md").write_text("---\nname: tdd\ndescription: Use when: x\n---\nbody\n")

        skill = loaded(directory)

        assert any("not valid YAML" in p for p in skill.problems)
        assert skill.body == "body"

    def test_the_rescue_ignores_lines_that_are_not_a_pair(self, skills_path: Path) -> None:
        directory = skills_path / "tdd"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\n# a comment\nname: tdd\nbare-line-with-no-colon\n"
            "description: Use when: x\n---\nbody\n"
        )

        skill = loaded(directory)

        assert skill.description == "Use when: x"
        assert "bare-line-with-no-colon" not in skill.metadata

    def test_a_non_string_frontmatter_value_is_read_as_text(self, write_skill: WriteSkill) -> None:
        """YAML happily produces ints, dates and booleans. Everything this package keeps is
        text, so a `version: 3` does not arrive as something a template cannot format."""
        skill = loaded(write_skill("tdd", frontmatter="version: 3\ndraft: true"))
        assert skill.metadata == {"version": "3", "draft": "True"}

    def test_the_rescue_drops_what_it_cannot_read_rather_than_guessing(
        self, skills_path: Path
    ) -> None:
        """A rescue, not a second YAML implementation. Nested and continuation lines go."""
        directory = skills_path / "tdd"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\nname: tdd\ndescription: Use when: x\nnested:\n  - one\n  - two\n---\nbody\n"
        )

        skill = loaded(directory)

        assert skill.description == "Use when: x"
        assert skill.metadata == {"nested": ""}

    def test_frontmatter_that_is_not_a_mapping_is_reported(self, skills_path: Path) -> None:
        directory = skills_path / "tdd"
        directory.mkdir()
        (directory / "SKILL.md").write_text("---\n- one\n- two\n---\nbody\n")

        assert any("not a mapping" in p for p in loaded(directory).problems)

    def test_empty_frontmatter_is_reported(self, skills_path: Path) -> None:
        directory = skills_path / "tdd"
        directory.mkdir()
        (directory / "SKILL.md").write_text("---\n---\nbody\n")

        assert any("frontmatter is empty" in p for p in loaded(directory).problems)


class TestBrokenSkills:
    def test_a_directory_with_no_skill_file(self, skills_path: Path) -> None:
        (skills_path / "notaskill").mkdir()

        result = load_skill(skills_path / "notaskill")

        assert isinstance(result, BrokenSkill)
        assert "no SKILL.md" in result.reason

    def test_an_unreadable_file(self, skills_path: Path) -> None:
        directory = skills_path / "tdd"
        directory.mkdir()
        (directory / "SKILL.md").write_bytes(b"\xff\xfe not utf-8 \xff")

        result = load_skill(directory)

        assert isinstance(result, BrokenSkill)
        assert "unreadable" in result.reason

    def test_broken_skills_are_surfaced_rather_than_skipped(
        self, library: SkillLibrary, skills_path: Path, write_skill: WriteSkill
    ) -> None:
        """A skill that vanished silently is indistinguishable from one never installed."""
        write_skill("tdd")
        (skills_path / "notaskill").mkdir()

        catalogue = library.catalogue()

        assert catalogue.ids() == ["tdd"]
        assert [broken.id for broken in catalogue.broken] == ["notaskill"]

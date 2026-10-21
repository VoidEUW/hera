"""The release notes are the changelog, so what turns commits into notes is tested.

The script lives in `.github/scripts/` because it is part of the release workflow and nothing
else imports it; the tests load it by path. Everything checked here is a pure function, so no
repository is needed -- the git calls are the thin part and a dry run of the workflow covers them.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "release_notes.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_notes", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_notes"] = module
    spec.loader.exec_module(module)
    return module


notes = _load()

TAGS = [
    "v0.1.0",
    "v0.2.0",
    "v0.2.1-rc1",
    "v0.2.1-rc2",
    "v0.2.1-rc10",
    "v0.2.1-rc9",
    "hera-prompts-v0.1.0",
    "hera-prompts-v0.1.3",
    "not-a-version",
]


class TestReadingACommit:
    def test_type_scope_subject_and_pull_request(self) -> None:
        entry = notes.parse_commit("feat(web): palette (#199)", "abc1234")

        assert (entry.kind, entry.scope, entry.subject, entry.number) == (
            "feat",
            "web",
            "palette",
            "199",
        )
        assert not entry.breaking

    def test_a_bang_is_a_breaking_change(self) -> None:
        assert notes.parse_commit("feat(api)!: drop v1", "abc").breaking

    def test_a_breaking_change_footer_is_one_too(self) -> None:
        assert notes.parse_commit("fix: tidy", "abc", "BREAKING CHANGE: the flag is gone").breaking

    def test_a_title_that_is_not_conventional_is_kept_whole(self) -> None:
        entry = notes.parse_commit("Update README.md (#178)", "abc")

        assert (entry.kind, entry.subject, entry.number) == ("other", "Update README.md", "178")

    def test_a_scope_is_optional(self) -> None:
        entry = notes.parse_commit("chore: tidy", "abc")

        assert (entry.kind, entry.scope) == ("chore", None)


class TestWhichTagComesBefore:
    def test_a_release_candidate_picks_up_from_the_newest_earlier_tag(self) -> None:
        assert notes.previous_tag("v0.2.1-rc2", TAGS) == "v0.2.1-rc1"

    def test_rc10_is_after_rc9(self) -> None:
        """Compared as numbers: as text `rc10` sorts before `rc9` and the range is wrong."""
        assert notes.previous_tag("v0.2.1-rc10", TAGS) == "v0.2.1-rc9"
        assert notes.previous_tag("v0.2.1", [*TAGS, "v0.2.1-rc10"]) == "v0.2.0"

    def test_a_final_release_skips_its_release_candidates(self) -> None:
        """So `v0.2.1` lists everything since `v0.2.0`, covering all of its rcs."""
        assert notes.previous_tag("v0.2.1", [*TAGS, "v0.2.1"]) == "v0.2.0"

    def test_the_first_tag_has_no_predecessor(self) -> None:
        assert notes.previous_tag("v0.1.0", TAGS) is None

    def test_a_package_only_looks_at_its_own_tags(self) -> None:
        assert notes.previous_tag("hera-prompts-v0.1.3", TAGS) == "hera-prompts-v0.1.0"
        assert notes.previous_tag("v0.2.0", TAGS) == "v0.1.0"

    def test_something_that_is_not_a_version_tag_has_none(self) -> None:
        assert notes.previous_tag("not-a-version", TAGS) is None

    @pytest.mark.parametrize(
        ("tag", "expected"),
        [("v0.2.1-rc4", True), ("v0.2.1", False), ("hera-prompts-v0.1.3-beta1", True)],
    )
    def test_a_suffix_makes_it_a_pre_release(self, tag: str, expected: bool) -> None:
        assert notes.is_prerelease(tag) is expected


def entries(*titles: str) -> list[object]:
    return [notes.parse_commit(title, f"sha{at}") for at, title in enumerate(titles)]


class TestRendering:
    def test_commits_are_grouped_by_type_in_a_fixed_order(self) -> None:
        text = notes.render(
            entries("docs: guide (#3)", "fix(api): crash (#2)", "feat(web): palette (#1)"),
            tag="v1.0.0",
            previous="v0.9.0",
            repo="o/r",
        )

        headings = [line for line in text.splitlines() if line.startswith("### ")]
        assert headings == ["### Features", "### Fixes", "### Documentation"]
        assert "- **web**: palette ([#1](https://github.com/o/r/pull/1))" in text

    def test_breaking_changes_come_first(self) -> None:
        text = notes.render(
            entries("feat: small (#1)", "feat(api)!: drop v1 (#2)"),
            tag="v1.0.0",
            previous=None,
            repo="o/r",
        )

        assert text.index("### Breaking changes") < text.index("### Features")
        assert "drop v1" in text.split("### Features")[0]

    def test_dependency_bumps_are_one_line_with_a_count(self) -> None:
        text = notes.render(
            entries(
                "chore(deps): bump a from 1 to 2 (#10)",
                "ci: bump actions/checkout from 4 to 7 (#11)",
                "chore: tidy (#12)",
            ),
            tag="v1.0.0",
            previous=None,
            repo="o/r",
        )

        assert "2 dependency updates" in text
        assert "bump a from" not in text
        assert "tidy" in text

    def test_a_pull_request_is_linked_and_a_bare_commit_shows_its_hash(self) -> None:
        text = notes.render(entries("Update README.md"), tag="v1.0.0", previous=None, repo="o/r")

        assert "`sha0`" in text

    def test_a_release_candidate_says_so(self) -> None:
        text = notes.render(entries("feat: x (#1)"), tag="v1.0.0-rc1", previous=None, repo="o/r")

        assert text.startswith("> **Pre-release.**")
        assert "`v1.0.0`" in text

    def test_a_final_release_does_not(self) -> None:
        text = notes.render(entries("feat: x (#1)"), tag="v1.0.0", previous=None, repo="o/r")

        assert "Pre-release" not in text

    def test_the_full_diff_is_linked_when_there_is_a_previous_tag(self) -> None:
        text = notes.render(entries("feat: x (#1)"), tag="v1.1.0", previous="v1.0.0", repo="o/r")

        assert text.endswith("**Full changelog**: https://github.com/o/r/compare/v1.0.0...v1.1.0\n")

    def test_no_commits_is_said_rather_than_left_blank(self) -> None:
        text = notes.render([], tag="v1.0.1", previous="v1.0.0", repo="o/r")

        assert "No changes since the previous tag." in text

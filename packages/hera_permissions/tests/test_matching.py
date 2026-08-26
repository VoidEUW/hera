"""Pattern matching and the one opinion in this package: what "more specific" means."""

from __future__ import annotations

import pytest

from hera_permissions import matches, specificity


@pytest.mark.parametrize(
    ("pattern", "tool", "expected"),
    [
        ("*", "fs__read", True),
        ("fs__*", "fs__read", True),
        ("fs__*", "shell__exec", False),
        ("fs__read", "fs__read", True),
        ("fs__read", "fs__readdir", False),
        ("fs__read?", "fs__reads", True),
        ("hera__*", "hera__emotion", True),
    ],
)
def test_patterns_match_tool_names(pattern: str, tool: str, expected: bool) -> None:
    assert matches(pattern, tool) is expected


def test_matching_is_case_sensitive() -> None:
    """Tool names are `server__tool` identifiers, not filenames. Two servers differing only in
    case is a collision worth seeing rather than smoothing over."""
    assert not matches("FS__*", "fs__read")


def test_an_exact_name_outranks_every_wildcard() -> None:
    assert specificity("fs__read") > specificity("fs__read*")


def test_a_longer_prefix_outranks_a_shorter_one() -> None:
    assert specificity("fs__*") > specificity("fs*") > specificity("*")


def test_a_character_class_never_outranks_a_literal_name() -> None:
    """`[seq]` works because fnmatch supports it; it should not win on character count."""
    assert specificity("fs__rea[dt]") < specificity("fs__read")

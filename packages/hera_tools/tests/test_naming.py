"""Namespaced names: what they may contain, and that they survive a round trip."""

from __future__ import annotations

import pytest
from hera_tools.errors import InvalidToolName
from hera_tools.naming import (
    MAX_NAME_LENGTH,
    is_overlong,
    qualify,
    split,
    validate_server_name,
)


def test_qualify_and_split_round_trip() -> None:
    assert qualify("fs", "read_file") == "fs__read_file"
    assert split("fs__read_file") == ("fs", "read_file")


def test_split_takes_the_first_separator() -> None:
    """A tool may contain the separator; a server may not, which makes this unambiguous."""
    assert split(qualify("fs", "read__file")) == ("fs", "read__file")


@pytest.mark.parametrize("server", ["my.server", "", "-leading", "with space", "über"])
def test_invalid_server_names_are_refused(server: str) -> None:
    with pytest.raises(InvalidToolName):
        validate_server_name(server)


def test_a_server_name_may_not_contain_the_separator() -> None:
    with pytest.raises(InvalidToolName):
        qualify("my__server", "read")


def test_a_tool_needs_a_name() -> None:
    with pytest.raises(InvalidToolName):
        qualify("fs", "")


@pytest.mark.parametrize("name", ["fs", "fs__", "__read", "", "fsread"])
def test_split_refuses_names_that_are_not_namespaced(name: str) -> None:
    with pytest.raises(InvalidToolName):
        split(name)


def test_overlong_names_are_flagged_but_not_refused() -> None:
    """Renaming would collide; refusing would lose a working tool. Flagging is the answer."""
    name = qualify("fs", "x" * MAX_NAME_LENGTH)
    assert is_overlong(name)
    assert not is_overlong(qualify("fs", "read"))

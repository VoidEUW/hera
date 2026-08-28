"""The data directory resolves from the environment, on every call."""

from __future__ import annotations

from pathlib import Path

import pytest

import hera_home
from hera_home import (
    chat_dir,
    chats_dir,
    config_path,
    database_path,
    home,
    mcp_path,
    mind_dir,
    scratch_dir,
    skills_dir,
)


def test_defaults_to_dot_hera_in_the_users_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(hera_home.HOME_ENV, raising=False)
    assert home() == Path("~/.hera").expanduser()


def test_the_environment_variable_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(hera_home.HOME_ENV, str(tmp_path))
    assert home() == tmp_path


def test_a_tilde_in_the_variable_is_expanded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(hera_home.HOME_ENV, "~/somewhere")
    assert home() == Path("~/somewhere").expanduser()


def test_an_empty_variable_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exporting the variable to "" is a shell accident, not a request for the CWD."""
    monkeypatch.setenv(hera_home.HOME_ENV, "")
    assert home() == Path("~/.hera").expanduser()


def test_the_answer_is_not_cached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A fixture that repoints the home mid-process must take effect immediately."""
    monkeypatch.setenv(hera_home.HOME_ENV, str(tmp_path / "first"))
    assert home() == tmp_path / "first"
    monkeypatch.setenv(hera_home.HOME_ENV, str(tmp_path / "second"))
    assert home() == tmp_path / "second"


def test_every_well_known_path_sits_under_the_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(hera_home.HOME_ENV, str(tmp_path))
    assert mind_dir() == tmp_path / "mind"
    assert skills_dir() == tmp_path / "skills"
    assert database_path() == tmp_path / "hera.sqlite3"
    assert mcp_path() == tmp_path / "mcp.json"
    assert config_path() == tmp_path / "config.toml"
    assert chats_dir() == tmp_path / "chats"
    assert chat_dir("c-1") == tmp_path / "chats" / "c-1"
    assert scratch_dir("c-1") == tmp_path / "chats" / "c-1" / "scratch"


def test_nothing_is_created_by_asking(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Asking where something is and deciding to make it are different decisions."""
    root = tmp_path / "absent"
    monkeypatch.setenv(hera_home.HOME_ENV, str(root))
    for path in (home(), mind_dir(), skills_dir(), database_path()):
        assert not path.exists()


@pytest.mark.parametrize("chat_id", ["", ".", "..", "../mind", "a/b", "a\\b", "/etc"])
def test_a_chat_id_that_is_not_one_path_segment_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, chat_id: str
) -> None:
    """The id reaches this from a tool call, so it reaches it from *somewhere*.

    A ``..`` here would put a scratchpad in the mind repository and a leading ``/`` would put it
    outside ``~/.hera`` altogether, and both of those are one string away from a directory this
    package hands to somebody who will write into it.
    """
    monkeypatch.setenv(hera_home.HOME_ENV, str(tmp_path))
    with pytest.raises(ValueError, match="not a usable chat id"):
        chat_dir(chat_id)


def test_a_chat_directory_is_not_created_by_asking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(hera_home.HOME_ENV, str(tmp_path))
    for path in (chats_dir(), chat_dir("c-1"), scratch_dir("c-1")):
        assert not path.exists()

"""``hera user …``: accounts from the host, where a shell is the credential (ADR 27)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from hera_accounts import Accounts
from hera_core.cli import main
from hera_core.settings import CoreSettings
from hera_storage import Database, StorageSettings


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "home"
    root.mkdir()
    monkeypatch.setenv("HERA_HOME", str(root))
    return root


def typed(monkeypatch: pytest.MonkeyPatch, *passwords: str) -> None:
    """What a person types at the two prompts, in order."""
    answers = iter(passwords)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(answers))


def database() -> Database:
    return Database(StorageSettings(url=CoreSettings().database_url()))


def test_the_first_account_is_an_admin_under_the_owner_id(
    home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    typed(monkeypatch, "a long password", "a long password")
    assert main(["user", "create", "Ada@Example.org", "--role", "admin", "--name", "Ada"]) == 0
    assert "Created ada@example.org as admin" in capsys.readouterr().out

    db = database()
    with db.session() as session:
        [user] = Accounts(session).users()
        assert user.id == CoreSettings().owner_id
        assert Accounts(session).verify("ada@example.org", "a long password") is not None
    db.dispose()


def test_the_first_account_may_not_be_a_plain_user(
    home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    typed(monkeypatch, "a long password", "a long password")
    assert main(["user", "create", "ben@example.org"]) == 1
    assert "has to be an admin" in capsys.readouterr().err


def test_two_different_passwords_are_refused(
    home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    typed(monkeypatch, "a long password", "a different one")
    assert main(["user", "create", "ada@example.org", "--role", "admin"]) == 1
    assert "not the same" in capsys.readouterr().err


def test_list_reset_and_set_role(
    home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["user", "list"]) == 0
    assert "No accounts yet" in capsys.readouterr().out

    monkeypatch.setattr("sys.stdin", io.StringIO("a long password\n"))
    assert main(["user", "create", "ada@example.org", "--role", "admin", "--password-stdin"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO("another password\n"))
    assert main(["user", "create", "ben@example.org", "--password-stdin"]) == 0
    capsys.readouterr()

    assert main(["user", "list"]) == 0
    listed = capsys.readouterr().out
    assert "ada@example.org\tadmin" in listed
    assert "ben@example.org\tuser" in listed

    db = database()
    with db.session() as session:
        ada = Accounts(session).by_email("ada@example.org")
        assert ada is not None
        Accounts(session).open_session(ada.id)
    db.dispose()

    typed(monkeypatch, "a fresh password", "a fresh password")
    assert main(["user", "reset-password", "ada@example.org"]) == 0
    assert "signed out of 1 session" in capsys.readouterr().out

    assert main(["user", "set-role", "ada@example.org", "user"]) == 1
    assert "only admin" in capsys.readouterr().err
    assert main(["user", "set-role", "ben@example.org", "admin"]) == 0
    assert main(["user", "set-role", "ada@example.org", "user"]) == 0
    assert "is now a user" in capsys.readouterr().out

    assert main(["user", "reset-password", "nobody@example.org"]) == 1
    assert "no account" in capsys.readouterr().err


def test_init_prints_the_setup_code_and_writes_it_down(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init"]) == 0
    out = capsys.readouterr().out
    code = (home / "setup-code").read_text().strip()
    assert code in out
    assert "Nobody can sign in yet" in out

"""Boot, migrations, the CLI, and the wiring.

The theme is that a fresh install works and an old one is refused loudly. ADR 7 has no
importer, so the dangerous failure is not "it does not work" — it is "it half works and writes
into the old directory".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlmodel import SQLModel

from hera_core.boot import LEGACY_DATABASE, LegacyHome, check_home, prepare
from hera_core.cli import main
from hera_core.migrations import upgrade_to_head
from hera_core.models import TABLE_NAMES
from hera_home import DATABASE_FILENAME
from hera_profiles import MindRepository, ProfileRepository
from hera_storage import Database


class TestRefusingAnOldHome:
    def test_a_missing_directory_is_a_fresh_install(self, tmp_path: Path) -> None:
        check_home(tmp_path / "nothing-here")

    def test_an_empty_directory_is_fine(self, tmp_path: Path) -> None:
        check_home(tmp_path)

    def test_the_old_database_file_stops_the_boot(self, tmp_path: Path) -> None:
        (tmp_path / LEGACY_DATABASE).write_text("")

        with pytest.raises(LegacyHome) as caught:
            check_home(tmp_path)

        assert LEGACY_DATABASE in str(caught.value)
        assert "mv " in str(caught.value), "the message must give the command"
        assert "deleted" in str(caught.value), "and say nothing was deleted"

    def test_nothing_is_deleted_by_the_refusal(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DATABASE
        legacy.write_text("precious")

        with pytest.raises(LegacyHome):
            check_home(tmp_path)

        assert legacy.read_text() == "precious"

    def test_legacy_tables_in_a_current_database_stop_the_boot(self, tmp_path: Path) -> None:
        """A half-migrated directory: the file has the right name and the wrong contents."""
        database = tmp_path / DATABASE_FILENAME
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE chats_legacy_v0 (id INTEGER)")

        with pytest.raises(LegacyHome):
            check_home(tmp_path)

    def test_a_current_database_passes(self, tmp_path: Path) -> None:
        database = tmp_path / DATABASE_FILENAME
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE chat_chats (id INTEGER)")

        check_home(tmp_path)

    def test_an_unreadable_file_is_left_to_the_engine(self, tmp_path: Path) -> None:
        """A guess from this function would be worse than the error SQLAlchemy produces."""
        (tmp_path / DATABASE_FILENAME).write_text("not a database at all")
        check_home(tmp_path)


class TestMigrations:
    def test_the_schema_matches_the_models(self, tmp_path: Path) -> None:
        """Autogenerate only sees tables that were imported, so a package nobody imported is a
        package whose tables silently do not exist."""
        database = Database.in_memory()
        upgrade_to_head(database)

        created = set(inspect(database.engine).get_table_names()) - {"alembic_version"}
        assert created == set(TABLE_NAMES)
        database.dispose()

    def test_every_registered_table_is_listed(self) -> None:
        """The guard that makes forgetting a package a failing test rather than a migration
        that quietly drops a table."""
        registered = {
            mapper.class_.__tablename__
            for mapper in SQLModel._sa_registry.mappers
            if str(mapper.class_.__tablename__).split("_")[0]
            in {"chat", "profile", "skill", "mem", "evo"}
        }
        assert registered == set(TABLE_NAMES)

    def test_running_it_twice_changes_nothing(self, tmp_path: Path) -> None:
        database = Database.in_memory()
        upgrade_to_head(database)
        upgrade_to_head(database)
        assert "chat_chats" in inspect(database.engine).get_table_names()
        database.dispose()

    def test_it_can_be_taken_back_down(self) -> None:
        """A downgrade nobody has run is a downgrade that does not work, and the moment it is
        needed is the worst moment to find that out."""
        from alembic import command

        from hera_core.migrations import alembic_config

        database = Database.in_memory()
        config = alembic_config(database)
        command.upgrade(config, "head")
        command.downgrade(config, "base")

        remaining = set(inspect(database.engine).get_table_names()) - {"alembic_version"}
        assert remaining == set()

        command.upgrade(config, "head")
        assert set(inspect(database.engine).get_table_names()) >= set(TABLE_NAMES)
        database.dispose()

    def test_all_tables_carry_a_package_prefix(self) -> None:
        """All models share one MetaData, so an unprefixed name from two packages collides."""
        for name in TABLE_NAMES:
            assert "_" in name


class TestPreparing:
    def test_a_fresh_install_gets_a_schema_a_mind_and_a_profile(self, tmp_path: Path) -> None:
        database = Database.in_memory()
        mind = MindRepository(tmp_path / "mind")
        owner = uuid4()

        prepare(database, mind, owner_id=owner)

        assert mind.initialised
        assert mind.read("character").strip()
        with database.session() as session:
            assert ProfileRepository(session).default_for(owner) is not None
        database.dispose()

    def test_it_is_idempotent(self, tmp_path: Path) -> None:
        """Runs on every boot, not only the first. A person who deletes a profile should get
        it back."""
        database = Database.in_memory()
        mind = MindRepository(tmp_path / "mind")
        owner = uuid4()

        prepare(database, mind, owner_id=owner)
        prepare(database, mind, owner_id=owner)

        with database.session() as session:
            assert len(ProfileRepository(session).for_owner(owner)) == 1
        database.dispose()


class TestTheCli:
    def test_check_reports_a_usable_directory(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["check"]) == 0
        assert "looks fine" in capsys.readouterr().out

    def test_check_refuses_an_old_one_without_a_traceback(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A person being told to move a directory. A stack trace buries the one line that
        matters (ADR 7)."""
        home = tmp_path / "old"
        home.mkdir()
        (home / LEGACY_DATABASE).write_text("")
        monkeypatch.setenv("HERA_HOME", str(home))

        assert main(["check"]) == 2
        assert "mv " in capsys.readouterr().err

    def test_init_prepares_the_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        home = tmp_path / "fresh"
        monkeypatch.setenv("HERA_HOME", str(home))
        monkeypatch.setenv("HERA_STORAGE_URL", f"sqlite:///{home / 'hera.sqlite3'}")
        home.mkdir()

        assert main(["init"]) == 0
        assert (home / "mind" / "character.md").is_file()
        out = capsys.readouterr().out
        assert "Ready" in out
        assert str(home) in out, "it must name the directory it actually used"

    def test_version_exits_cleanly(self) -> None:
        with pytest.raises(SystemExit) as caught:
            main(["--version"])
        assert caught.value.code == 0

    def test_no_command_is_an_error(self) -> None:
        with pytest.raises(SystemExit) as caught:
            main([])
        assert caught.value.code == 2

"""Engine construction, pragmas and the transaction boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from models import Doodad, Widget
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.pool import QueuePool, StaticPool
from sqlmodel import SQLModel, select

from hera_storage import Conflict, Database, StorageSettings


def _pragma(database: Database, name: str) -> Any:
    with database.session() as session:
        return session.execute(text(f"PRAGMA {name}")).scalar_one()


def _widget_count(database: Database) -> int:
    with database.session() as session:
        return len(session.exec(select(Widget)).all())


# -- construction --------------------------------------------------------------


def test_default_settings_match_the_contract() -> None:
    settings = StorageSettings()
    assert settings.url == "sqlite:///hera.db"
    assert settings.echo is False
    assert settings.sqlite_wal is True
    assert settings.busy_timeout_ms == 5000
    assert settings.pool_size == 5


def test_from_env_reads_the_prefixed_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERA_STORAGE_URL", "sqlite://")
    monkeypatch.setenv("HERA_STORAGE_ECHO", "true")
    monkeypatch.setenv("HERA_STORAGE_BUSY_TIMEOUT_MS", "1234")

    database = Database.from_env()
    try:
        assert database.engine.echo is True
        assert _pragma(database, "busy_timeout") == 1234
    finally:
        database.dispose()


def test_url_keyword_overrides_the_settings() -> None:
    database = Database(StorageSettings(url="sqlite:///should-not-be-used.db"), url="sqlite://")
    try:
        assert database.engine.url.database in (None, "", ":memory:")
    finally:
        database.dispose()


def test_in_memory_uses_a_static_pool_and_one_shared_database(db: Database) -> None:
    assert isinstance(db.engine.pool, StaticPool)

    with db.session() as session:
        session.add(Widget(name="shared"))

    # Without StaticPool the next connection would open its own, empty database.
    assert _widget_count(db) == 1


def test_pool_size_is_applied_to_pooled_engines(tmp_path: Path) -> None:
    settings = StorageSettings(url=f"sqlite:///{tmp_path / 'pool.db'}", pool_size=3)
    database = Database(settings)
    try:
        pool = database.engine.pool
        assert isinstance(pool, QueuePool)
        assert pool.size() == 3
    finally:
        database.dispose()


def test_metadata_is_the_shared_sqlmodel_metadata(db: Database) -> None:
    assert db.metadata is SQLModel.metadata


def test_dispose_drops_the_pooled_connections(db: Database) -> None:
    db.dispose()
    with db.session() as session:
        session.execute(text("SELECT 1"))


# -- transaction boundary ------------------------------------------------------


def test_session_rolls_back_on_exception(db: Database) -> None:
    with pytest.raises(RuntimeError, match="boom"), db.session() as session:
        session.add(Widget(name="doomed"))
        session.flush()
        raise RuntimeError("boom")

    assert _widget_count(db) == 0


def test_session_commits_on_success(db: Database) -> None:
    with db.session() as session:
        session.add(Widget(name="kept"))

    assert _widget_count(db) == 1


def test_unique_violation_becomes_conflict(db: Database) -> None:
    with pytest.raises(Conflict) as excinfo, db.session() as session:
        session.add(Doodad(code="same"))
        session.add(Doodad(code="same"))

    assert isinstance(excinfo.value.__cause__, IntegrityError)

    with db.session() as session:
        assert session.exec(select(Doodad)).all() == []


def test_other_database_errors_are_not_swallowed(db: Database) -> None:
    """Only IntegrityError is translated; everything else surfaces unchanged."""
    with pytest.raises(OperationalError), db.session() as session:
        session.execute(text("SELECT * FROM a_table_that_does_not_exist"))


def test_dependency_yields_a_working_session_and_commits(db: Database) -> None:
    get_session = db.dependency()

    generator = get_session()
    session = next(generator)
    session.add(Widget(name="via-dependency"))
    with pytest.raises(StopIteration):
        next(generator)

    assert _widget_count(db) == 1


# -- sqlite pragmas ------------------------------------------------------------


def test_wal_is_enabled_on_a_file_database(tmp_path: Path) -> None:
    database = Database(url=f"sqlite:///{tmp_path / 'wal.db'}")
    try:
        assert _pragma(database, "journal_mode") == "wal"
    finally:
        database.dispose()


def test_wal_can_be_turned_off(tmp_path: Path) -> None:
    settings = StorageSettings(url=f"sqlite:///{tmp_path / 'nowal.db'}", sqlite_wal=False)
    database = Database(settings)
    try:
        assert _pragma(database, "journal_mode") != "wal"
    finally:
        database.dispose()


def test_foreign_keys_are_enforced(db: Database) -> None:
    assert _pragma(db, "foreign_keys") == 1


def test_busy_timeout_is_applied(tmp_path: Path) -> None:
    settings = StorageSettings(url=f"sqlite:///{tmp_path / 'busy.db'}", busy_timeout_ms=250)
    database = Database(settings)
    try:
        assert _pragma(database, "busy_timeout") == 250
    finally:
        database.dispose()

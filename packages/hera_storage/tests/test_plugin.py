"""The pytest11 entry point: fixtures arrive without any local conftest setup.

Nothing in this module registers a plugin or builds a database -- that is the point.
"""

from __future__ import annotations

from models import Widget
from sqlmodel import Session, select

from hera_storage import Database, Repository


def test_session_fixture_is_ready_to_use(session: Session) -> None:
    Repository(Widget, session).add(Widget(name="from-the-plugin"))
    assert len(session.exec(select(Widget)).all()) == 1


def test_db_fixture_is_isolated_per_test(session: Session) -> None:
    """The previous test committed a row; this one must not see it."""
    assert session.exec(select(Widget)).all() == []


def test_db_fixture_exposes_the_database(db: Database) -> None:
    assert isinstance(db, Database)
    with db.session() as session:
        assert session.exec(select(Widget)).all() == []

"""pytest fixtures, shipped to every library that installs this package.

Registered through the ``pytest11`` entry point, so downstream libraries write
``def test_x(session): ...`` with no conftest.py of their own.

Importing this module requires pytest; it is not part of the runtime dependencies and
nothing else in ``hera_storage`` imports it.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlmodel import Session

from .database import Database


@pytest.fixture
def db() -> Iterator[Database]:
    """A fresh in-memory database per test, with every registered table created.

    Only models imported by the time the fixture runs end up in the schema -- importing
    them at test-module level is enough.
    """
    database = Database.in_memory()
    database.create_all()
    try:
        yield database
    finally:
        database.dispose()


@pytest.fixture
def session(db: Database) -> Iterator[Session]:
    """A session inside one unit of work.

    The commit happens at teardown, so a test that expects :class:`~hera_storage.Conflict`
    on commit should open its own ``db.session()`` block instead of using this fixture.
    """
    with db.session() as active:
        yield active

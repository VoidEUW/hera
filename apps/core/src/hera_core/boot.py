"""What has to be true before the first request.

Two jobs, in order: refuse to run against a data directory from before v0.1, then make the
things a fresh install needs exist.

The refusal is [ADR 7](../../../docs/adr/0007-fresh-start-no-legacy-import.md). There is no
importer from the previous version — its schema, its prompts and its tool grammar are all
wrong now — and the dangerous failure is not "it does not work", it is "it half works and
writes into the old directory". So boot looks for the old shape, stops, and says what to move
aside. **Nothing is ever deleted for you.**
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import UUID

from hera_core.migrations import upgrade_to_head
from hera_home import DATABASE_FILENAME, home
from hera_profiles import MindRepository, ProfileRepository
from hera_storage import Database

LEGACY_DATABASE = "hera.db"
"""The previous version's SQLite file. Its presence is the marker."""

LEGACY_TABLE_HINT = "_legacy_v0"
"""Substring of the table names a half-migrated pre-v0.1 directory carries."""


class LegacyHome(RuntimeError):
    """The data directory belongs to a version before v0.1.

    Not a warning and not something to work around. The message names the directory, says what
    was found, and gives the one command that resolves it.
    """


def check_home(root: Path | None = None) -> None:
    """Refuse a pre-v0.1 ``~/.hera``. Cheap, and runs on every boot.

    A missing directory is fine — that is a fresh install, which is the supported starting
    point. What is not fine is one holding ``hera.db``, or a v0.1 database that somebody has
    poured old tables into.
    """
    root = root if root is not None else home()
    if not root.is_dir():
        return

    legacy = root / LEGACY_DATABASE
    if legacy.exists():
        raise LegacyHome(
            f"{root} holds {LEGACY_DATABASE}, which belongs to a version of Hera from before "
            f"v0.1. There is no importer (ADR 7). Move the directory aside and start fresh:\n"
            f"    mv {root} {root}.pre-v0.1\n"
            f"Nothing has been deleted."
        )

    current = root / DATABASE_FILENAME
    if current.exists() and _has_legacy_tables(current):
        raise LegacyHome(
            f"{current} contains tables from before v0.1. Move {root} aside and start fresh; "
            f"nothing has been deleted."
        )


def _has_legacy_tables(database: Path) -> bool:
    """Look for the old table names without importing anything.

    Read-only and through plain ``sqlite3``: this runs before the engine exists, and opening
    the file with SQLAlchemy would apply pragmas to a database we have just decided we may not
    want to touch.
    """
    try:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE ?",
                (f"%{LEGACY_TABLE_HINT}%",),
            ).fetchall()
    except sqlite3.Error:
        # Unreadable, locked, or not a database. Not our call to make here -- the engine will
        # produce a much better error than a guess from this function would.
        return False
    return bool(rows)


def prepare(database: Database, mind: MindRepository, *, owner_id: UUID) -> None:
    """Make a fresh install usable: the schema, the mind, and one profile.

    Idempotent, so it runs on every boot rather than only on the first. A person who deletes a
    profile or a mind file should get it back, and discovering on the first turn that there is
    nobody to answer as is a worse way to find out.
    """
    upgrade_to_head(database)
    mind.ensure()
    with database.session() as session:
        ProfileRepository(session).ensure_default_exists(owner_id)

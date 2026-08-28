"""What has to be true before the first request.

Three jobs, in order: refuse to run against a data directory from before v0.1, refuse one whose
schema is *ahead* of this build, then make the things a fresh install needs exist.

The first refusal is [ADR 7](../../../docs/adr/0007-fresh-start-no-legacy-import.md). There is no
importer from the previous version — its schema, its prompts and its tool grammar are all
wrong now — and the dangerous failure is not "it does not work", it is "it half works and
writes into the old directory". So boot looks for the old shape, stops, and says what to move
aside. **Nothing is ever deleted for you.**

The second is the everyday one, and it is about *going backwards*: checking out an older branch,
or downgrading Hera, against a `~/.hera` that a newer build has already migrated. Alembic's own
answer to that is a forty-line traceback ending in ``Can't locate revision identified by
'0004'``, which says nothing about what to do. This says it in a sentence.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import UUID

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError

from hera_core.migrations import alembic_config, upgrade_to_head
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


class DatabaseAhead(RuntimeError):
    """The database has been migrated by a build newer than this one.

    Its own exception rather than a `LegacyHome`, because the remedy is the opposite: nothing is
    wrong with the directory and nothing should be moved aside. The code is behind, and either
    the code or the database has to move.
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


def check_revision(database: Database) -> None:
    """Refuse a database stamped with a revision this build does not have.

    The ordinary way to arrive here is checking out an older branch — or downgrading Hera —
    against a ``~/.hera`` a newer build already migrated. Alembic notices, but only as
    ``Can't locate revision identified by '0004'`` under forty lines of its own frames, at a
    point where the reader has no reason to connect it to the branch they just switched to.

    **Refusing rather than repairing is the whole point.** Stamping the database back would
    leave columns behind that a later upgrade then fails to add; downgrading it would drop
    somebody's data because their shell was in the wrong directory. Both are decisions for a
    person, so this names the revision, names the file, and gives the command.

    A database with no ``alembic_version`` row at all is a fresh one and is fine — that is what
    :func:`prepare` is about to create.
    """
    script = ScriptDirectory.from_config(alembic_config(database))
    with database.engine.connect() as connection:
        stamped = MigrationContext.configure(connection).get_current_heads()

    unknown = [revision for revision in stamped if _missing(script, revision)]
    if not unknown:
        return

    head = script.get_current_head() or "nothing"
    # The engine's own URL, not `home() / DATABASE_FILENAME`: `HERA_STORAGE_URL` can point
    # somewhere else entirely, and an error naming a file it did not look at is worse than one
    # naming no file at all.
    where = database.engine.url.database or str(database.engine.url)
    raise DatabaseAhead(
        f"{where} is at migration {', '.join(unknown)}, which this build of Hera does not "
        f"have — it knows up to {head}. The database was migrated by a newer version, so "
        f"either the code is behind or the wrong branch is checked out.\n"
        f"  Go forward:  git switch <the branch that has {unknown[0]}>\n"
        f"  Or go back:  on that branch, uv run alembic downgrade {head}\n"
        f"Nothing has been changed."
    )


def _missing(script: ScriptDirectory, revision: str) -> bool:
    try:
        return script.get_revision(revision) is None
    except CommandError:
        # What alembic raises for a revision it cannot resolve, which is precisely the case
        # this function exists to report. Anything else is a broken migrations directory and
        # deserves to propagate.
        return True


def prepare(database: Database, mind: MindRepository, *, owner_id: UUID) -> None:
    """Make a fresh install usable: the schema, the mind, and one profile.

    Idempotent, so it runs on every boot rather than only on the first. A person who deletes a
    profile or a mind file should get it back, and discovering on the first turn that there is
    nobody to answer as is a worse way to find out.
    """
    check_revision(database)
    upgrade_to_head(database)
    mind.ensure()
    with database.session() as session:
        ProfileRepository(session).ensure_default_exists(owner_id)

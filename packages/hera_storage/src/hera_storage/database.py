"""Engine and session management.

Synchronous on purpose: the target is SQLite on a single-user machine, where a query
costs microseconds and all real latency sits in LLM calls. The API is nevertheless
thread-safe in the only way that matters -- :meth:`Database.session` hands out a fresh
session per call and never shares one globally.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, MetaData, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool
from sqlmodel import Session, SQLModel

from .errors import Conflict
from .settings import StorageSettings

_IN_MEMORY_NAMES = (None, "", ":memory:")


class Database:
    """Owns one engine and produces sessions from it.

    Create a single instance per process and share it; sessions are per unit of work.
    """

    def __init__(self, settings: StorageSettings | None = None, *, url: str | None = None) -> None:
        resolved = settings if settings is not None else StorageSettings()
        if url is not None:
            resolved = resolved.model_copy(update={"url": url})
        self._settings = resolved
        self._engine = _build_engine(resolved)

    @classmethod
    def from_env(cls) -> Database:
        """Build from ``HERA_STORAGE_*`` environment variables."""
        return cls(StorageSettings())

    @classmethod
    def in_memory(cls) -> Database:
        """Throwaway in-memory SQLite database, for tests.

        Uses a ``StaticPool`` so that every connection sees the same database -- with the
        default pooling each new connection would open its own empty one.
        """
        return cls(StorageSettings(url="sqlite://", sqlite_wal=False))

    @property
    def engine(self) -> Engine:
        return self._engine

    @property
    def metadata(self) -> MetaData:
        """The shared ``SQLModel.metadata``, carrying every model of every hera library.

        This is what ``alembic autogenerate`` in heraAPI points its ``target_metadata`` at.
        """
        return SQLModel.metadata

    @contextmanager
    def session(self) -> Iterator[Session]:
        """A unit of work: commits on success, rolls back on any exception, always closes.

        This is the only place that commits. Repositories merely flush, so several writes
        -- across several repositories -- form one atomic transaction.
        """
        session = Session(self._engine)
        try:
            yield session
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise Conflict(str(exc.orig)) from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dependency(self) -> Callable[[], Iterator[Session]]:
        """A FastAPI dependency: ``session: Session = Depends(db.dependency())``."""

        def get_session() -> Iterator[Session]:
            with self.session() as session:
                yield session

        return get_session

    def create_all(self) -> None:
        """Create every registered table. For tests and bootstrapping only -- production
        schema changes belong in the Alembic migrations of heraAPI."""
        SQLModel.metadata.create_all(self._engine)

    def dispose(self) -> None:
        """Close all pooled connections."""
        self._engine.dispose()


def _build_engine(settings: StorageSettings) -> Engine:
    url = make_url(settings.url)
    is_sqlite = url.get_backend_name() == "sqlite"
    is_memory = is_sqlite and url.database in _IN_MEMORY_NAMES

    kwargs: dict[str, Any] = {"echo": settings.echo}
    if is_memory:
        # StaticPool keeps the one connection that holds the database alive; without
        # check_same_thread=False that connection could not be reused across threads.
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # StaticPool and SingletonThreadPool reject pool_size, hence the branch.
        kwargs["pool_size"] = settings.pool_size

    engine = create_engine(url, **kwargs)
    if is_sqlite:
        _register_sqlite_pragmas(
            engine,
            # WAL is meaningless for an in-memory database, which has no journal file.
            wal=settings.sqlite_wal and not is_memory,
            busy_timeout_ms=settings.busy_timeout_ms,
        )
    return engine


def _register_sqlite_pragmas(engine: Engine, *, wal: bool, busy_timeout_ms: int) -> None:
    """Apply the pragmas on every new connection -- they are per-connection, not per-file."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(
        dbapi_connection: DBAPIConnection, _record: ConnectionPoolEntry
    ) -> None:
        cursor = dbapi_connection.cursor()
        try:
            if wal:
                cursor.execute("PRAGMA journal_mode=WAL")
            # Off by default in SQLite; without it foreign keys are decoration.
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        finally:
            cursor.close()

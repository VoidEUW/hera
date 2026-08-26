"""Configuration for the storage layer, read from ``HERA_STORAGE_*`` environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    """Connection settings for :class:`hera_storage.Database`.

    Every field can be overridden through an environment variable with the
    ``HERA_STORAGE_`` prefix, e.g. ``HERA_STORAGE_URL=postgresql+psycopg://...``.
    """

    model_config = SettingsConfigDict(env_prefix="HERA_STORAGE_", extra="ignore")

    url: str = "sqlite:///hera.db"
    """SQLAlchemy database URL. SQLite is the primary target, PostgreSQL works unchanged."""

    echo: bool = False
    """Log every emitted SQL statement."""

    sqlite_wal: bool = True
    """Enable write-ahead logging on file-backed SQLite databases."""

    busy_timeout_ms: int = 5000
    """How long SQLite waits for a lock before raising ``database is locked``."""

    pool_size: int = 5
    """Connection pool size. Ignored for in-memory SQLite, which uses a StaticPool."""

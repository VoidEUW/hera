"""Alembic, and the one function the application calls.

Migrations live here because this is the only place that imports every package, so it is the
only place ``alembic autogenerate`` sees the whole schema (ARCHITECTURE.md). Importing this
module imports every model as a side effect, which is what puts them into the shared
``SQLModel.metadata`` that ``env.py`` points at.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

# Imported for the side effect: every model has to be registered into the shared MetaData
# before autogenerate can see it, and this is the module that guarantees they all are.
from hera_core.models import ALL_TABLES
from hera_storage import Database

HERE = Path(__file__).resolve().parent

__all__ = ["ALL_TABLES", "alembic_config", "upgrade_to_head"]


def alembic_config(database: Database) -> Config:
    """An Alembic config pointed at this package's ``versions/`` and one engine.

    Built in code rather than read from ``alembic.ini``, because the URL is decided at boot
    from ``HERA_HOME`` and a file would be a second place that has an opinion about it.
    """
    config = Config()
    config.set_main_option("script_location", str(HERE))
    config.set_main_option("sqlalchemy.url", str(database.engine.url))
    config.attributes["connection"] = None
    config.attributes["database"] = database
    return config


def upgrade_to_head(database: Database) -> None:
    """Bring the schema up to date. Idempotent, and safe on an empty database."""
    command.upgrade(alembic_config(database), "head")

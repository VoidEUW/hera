"""Alembic's entry point.

Online only: Hera's database is a local SQLite file, and there is nothing to hand a SQL script
to. ``render_as_batch=True`` is not optional — SQLite cannot ``ALTER COLUMN``, and batch mode
is what turns an alteration into the copy-and-swap it has to be. It relies on every constraint
having a deterministic name, which is why ``hera_storage`` sets a naming convention on the
shared metadata at import time.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Registers every table into SQLModel.metadata. Without this import autogenerate would compare
# the database against an empty schema and cheerfully propose dropping everything.
import hera_core.models  # noqa: F401

config = context.config
target_metadata = SQLModel.metadata


def run_migrations_online() -> None:
    database = config.attributes.get("database")
    if database is not None:
        connectable = database.engine
    else:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()

"""Every table in the system, imported in one place.

Nothing is defined here. All models share one ``SQLModel.metadata``, and a model is only in it
once its module has been imported — so ``alembic autogenerate`` sees exactly the tables that
happen to have been imported by the time it runs. Left implicit, that means a package nobody
imported first is a package whose tables silently do not exist.

This module makes it explicit and testable: ``test_migrations.py`` holds :data:`ALL_TABLES`
against the metadata, so forgetting a package here fails a test rather than producing a
migration that quietly drops a table.
"""

from __future__ import annotations

from hera_chats.models import Chat, Message, Project
from hera_profiles.models import Profile
from hera_skillsets.models import SkillUsage
from sqlmodel import SQLModel

ALL_TABLES: tuple[type[SQLModel], ...] = (Profile, SkillUsage, Project, Chat, Message)
"""Every table, in dependency-free order. Cross-package references are bare UUIDs, so there is
no ordering constraint to respect — which is exactly why that rule exists."""

TABLE_NAMES: frozenset[str] = frozenset(str(model.__tablename__) for model in ALL_TABLES)

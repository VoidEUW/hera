"""Domain-free persistence foundation.

Contains no table and no domain concept -- only the plumbing that every hera library
shares. It would work unchanged in a recipe manager.
"""

from __future__ import annotations

from .base import (
    NAMING_CONVENTION,
    Entity,
    EntityStatus,
    SoftDeletable,
    UTCDateTime,
    Versioned,
    utcnow,
)
from .database import Database
from .errors import Conflict, NotFound, StorageError
from .repository import Repository
from .settings import StorageSettings
from .versioning import MAX_VERSION_CHAIN, current_version, new_version, version_history

__all__ = [
    "MAX_VERSION_CHAIN",
    "NAMING_CONVENTION",
    "Conflict",
    "Database",
    "Entity",
    "EntityStatus",
    "NotFound",
    "Repository",
    "SoftDeletable",
    "StorageError",
    "StorageSettings",
    "UTCDateTime",
    "Versioned",
    "current_version",
    "new_version",
    "utcnow",
    "version_history",
]

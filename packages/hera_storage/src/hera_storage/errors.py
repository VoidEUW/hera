"""Exception hierarchy raised by this library."""

from __future__ import annotations

from uuid import UUID


class StorageError(Exception):
    """Base class for every error raised by ``hera_storage``."""


class NotFound(StorageError):
    """A row was requested by primary key but does not exist (or is revoked)."""

    def __init__(self, model_name: str, id: UUID) -> None:
        self.model_name = model_name
        self.id = id
        super().__init__(f"{model_name} with id {id} not found")


class Conflict(StorageError):
    """A write violated a database constraint.

    Raised by :meth:`hera_storage.Database.session` when the underlying commit fails
    with an ``IntegrityError``. The original exception is available as ``__cause__``.
    """

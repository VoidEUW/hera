"""Generic data access for any SQLModel table.

Meant to be subclassed. A domain library writes::

    class RecipeRepository(Repository[Recipe]):
        def __init__(self, session: Session) -> None:
            super().__init__(Recipe, session)

        def by_cuisine(self, cuisine: str) -> list[Recipe]:
            return self.list(Recipe.cuisine == cuisine, order_by=Recipe.title)

No method here commits. Writes are flushed so ids and constraint violations surface
immediately, but the transaction ends where it was opened -- in
:meth:`hera_storage.Database.session`.
"""

from __future__ import annotations

import builtins
from collections.abc import Iterable
from typing import Any, Generic, TypeVar, cast
from uuid import UUID

from sqlmodel import Session, SQLModel, func, select

from .base import Entity, EntityStatus, SoftDeletable, utcnow
from .errors import NotFound

T = TypeVar("T", bound=SQLModel)

# The public signatures are fixed by contract: an explicit TypeVar plus Generic[T], and
# `Any` for the SQLAlchemy filter expressions that have no useful narrower type. Hence
# UP046 and ANN401 are switched off for this module in pyproject.toml.
#
# `list` is one of those contracted method names, and it shadows the builtin inside the
# class body -- which is why return annotations here spell out `builtins.list`.


class Repository(Generic[T]):
    """CRUD for one model, bound to one session."""

    def __init__(self, model: type[T], session: Session) -> None:
        self.model = model
        self.session = session
        self._soft_deletable = issubclass(model, SoftDeletable)
        self._has_default_order = issubclass(model, Entity)

    # -- reading ---------------------------------------------------------------

    def get(self, id: UUID, *, include_revoked: bool = False) -> T | None:
        """Fetch by primary key, or ``None``."""
        obj = self.session.get(self.model, id)
        if obj is None:
            return None
        if self._hides_revoked(include_revoked) and _is_revoked(obj):
            return None
        return obj

    def get_or_raise(self, id: UUID, *, include_revoked: bool = False) -> T:
        """Fetch by primary key, or raise :class:`~hera_storage.NotFound`."""
        obj = self.get(id, include_revoked=include_revoked)
        if obj is None:
            raise NotFound(self.model.__name__, id)
        return obj

    def list(
        self,
        *where: Any,
        order_by: Any = None,
        limit: int | None = None,
        offset: int = 0,
        include_revoked: bool = False,
    ) -> builtins.list[T]:
        """Query rows, ordered by ``(created_at, id)`` unless told otherwise.

        The default order is deterministic on purpose: an unordered query may come back in
        a different order on every call, and ``limit``/``offset`` would then skip or repeat
        rows between pages. ``created_at`` alone is not enough -- bulk inserts share a
        timestamp -- hence the ``id`` tiebreaker.

        An explicit ``order_by`` replaces the default entirely, tiebreaker included. Models
        that do not inherit :class:`~hera_storage.Entity` have no default order.
        """
        statement = select(self.model)
        if self._hides_revoked(include_revoked):
            statement = statement.where(_not_revoked(self.model))
        for condition in where:
            statement = statement.where(condition)
        if order_by is not None:
            statement = statement.order_by(order_by)
        elif self._has_default_order:
            statement = statement.order_by(
                _column(self.model, "created_at"), _column(self.model, "id")
            )
        if offset:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def count(self, *where: Any, include_revoked: bool = False) -> int:
        """Count rows without loading them."""
        statement = select(func.count()).select_from(self.model)
        if self._hides_revoked(include_revoked):
            statement = statement.where(_not_revoked(self.model))
        for condition in where:
            statement = statement.where(condition)
        return int(self.session.exec(statement).one())

    def exists(self, id: UUID) -> bool:
        """Whether a row with this id exists. Revoked rows count as absent."""
        return self.count(_column(self.model, "id") == id) > 0

    # -- writing ---------------------------------------------------------------

    def add(self, obj: T) -> T:
        """Insert one row and flush, so its id and any constraint violation are immediate."""
        self.session.add(obj)
        self.session.flush()
        return obj

    def add_all(self, objs: Iterable[T]) -> builtins.list[T]:
        """Insert many rows in a single flush."""
        items = list(objs)
        self.session.add_all(items)
        self.session.flush()
        return items

    def save(self, obj: T) -> T:
        """Persist changes to an existing instance.

        Instances that belong to this session are flushed as they are. Detached ones --
        an object rebuilt from a request payload, say -- go through ``merge``, so the
        **returned** instance is the managed one; the argument stays detached.

        ``updated_at`` takes care of itself: the column's ``onupdate`` runs inside the
        UPDATE statement and the new value is written back onto the instance.
        """
        merged = self.session.merge(obj) if obj not in self.session else obj
        self.session.add(merged)
        self.session.flush()
        return merged

    def revoke(self, id: UUID) -> T:
        """Soft-delete: mark the row revoked and stamp ``revoked_at``."""
        self._require_soft_deletable("revoke")
        obj = self.get_or_raise(id, include_revoked=True)
        target = cast(SoftDeletable, obj)
        target.status = EntityStatus.REVOKED
        target.revoked_at = utcnow()
        self.session.flush()
        return obj

    def restore(self, id: UUID) -> T:
        """Undo a :meth:`revoke`."""
        self._require_soft_deletable("restore")
        obj = self.get_or_raise(id, include_revoked=True)
        target = cast(SoftDeletable, obj)
        target.status = EntityStatus.ACTIVE
        target.revoked_at = None
        self.session.flush()
        return obj

    def hard_delete(self, id: UUID) -> None:
        """Delete the row for good. Works on revoked rows too."""
        obj = self.get_or_raise(id, include_revoked=True)
        self.session.delete(obj)
        self.session.flush()

    # -- internals -------------------------------------------------------------

    def _hides_revoked(self, include_revoked: bool) -> bool:
        """``include_revoked`` is ignored on models that are not soft-deletable."""
        return self._soft_deletable and not include_revoked

    def _require_soft_deletable(self, operation: str) -> None:
        if not self._soft_deletable:
            raise TypeError(
                f"{operation}() requires {self.model.__name__} to inherit from SoftDeletable"
            )


def _is_revoked(obj: SQLModel) -> bool:
    return cast(SoftDeletable, obj).status == EntityStatus.REVOKED


def _not_revoked(model: type[SQLModel]) -> Any:
    return _column(model, "status") != EntityStatus.REVOKED


def _column(model: type[SQLModel], name: str) -> Any:
    """Reach a mapped column off a generic model class, past the type checker.

    ``type[T]`` says nothing about which fields exist, but every caller here has already
    established that the model carries the column.
    """
    return getattr(model, name)

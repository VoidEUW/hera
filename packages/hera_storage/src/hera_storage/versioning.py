"""Snapshot versioning for models built on :class:`~hera_storage.Versioned`.

Every version is a full row of its own, linked to its predecessor through
``supersedes_id``. No diffs: reading an old version is a plain primary-key lookup, and
the chain survives arbitrary schema evolution of the model.

Like the repository, none of these functions commit.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, cast
from uuid import UUID

from sqlmodel import Session, SQLModel, select

# The three public signatures are fixed by contract (an explicit TypeVar, `**changes: Any`),
# so UP047 and ANN401 are switched off for this module in pyproject.toml.

MAX_VERSION_CHAIN = 1000
"""Hard stop when walking a chain.

``supersedes_id`` carries no foreign key and nothing at the database level forbids a
cycle. Rather than trusting the data, every walk is bounded -- a corrupted chain
truncates the result instead of hanging the process.
"""


class _VersionedEntity(Protocol):
    """Structural type: what :func:`new_version` and friends actually need.

    Spelled as a protocol so the public API keeps ``Entity`` and ``Versioned`` as separate,
    freely combinable mixins instead of forcing a combined base class on callers.
    """

    id: UUID
    version: int
    supersedes_id: UUID | None
    origin: str | None
    is_current: bool


V = TypeVar("V", bound=_VersionedEntity)

_RESET_ON_COPY = ("id", "created_at", "updated_at")


def new_version(session: Session, obj: V, *, origin: str, **changes: Any) -> V:
    """Write a new version of ``obj`` and return it.

    The new row is a full copy carrying ``**changes``, with a fresh ``id``, ``version``
    incremented, ``supersedes_id`` pointing back at ``obj`` and ``is_current=True``.
    ``obj`` keeps its data and is flagged ``is_current=False``.
    """
    model = type(obj)
    data = cast(SQLModel, obj).model_dump()
    for field in _RESET_ON_COPY:
        data.pop(field, None)
    data.update(changes)
    data.update(
        version=obj.version + 1,
        supersedes_id=obj.id,
        origin=origin,
        is_current=True,
    )

    successor = model(**data)
    obj.is_current = False
    session.add(obj)
    session.add(successor)
    session.flush()
    return successor


def version_history(session: Session, model: type[V], id: UUID) -> list[V]:
    """All versions up to and including ``id``, oldest first.

    Walks ``supersedes_id`` backwards, so versions created *after* ``id`` are not
    included -- pass the id of the current version to see the whole chain. An unknown id
    yields an empty list.
    """
    chain: list[V] = []
    seen: set[UUID] = set()
    current = session.get(model, id)

    while current is not None and len(chain) < MAX_VERSION_CHAIN:
        if current.id in seen:
            break
        seen.add(current.id)
        chain.append(current)
        predecessor = current.supersedes_id
        current = None if predecessor is None else session.get(model, predecessor)

    chain.reverse()
    return chain


def current_version(session: Session, model: type[V], id: UUID) -> V | None:
    """The newest version of the chain that ``id`` belongs to, or ``None`` if unknown.

    Walks ``supersedes_id`` forwards, which works from any version in the chain --
    including one whose ``is_current`` flag was never cleared.
    """
    current = session.get(model, id)
    if current is None:
        return None

    seen: set[UUID] = {current.id}
    for _ in range(MAX_VERSION_CHAIN):
        successor = _successor_of(session, model, current.id)
        if successor is None or successor.id in seen:
            break
        seen.add(successor.id)
        current = successor
    return current


def _successor_of(session: Session, model: type[V], id: UUID) -> V | None:
    statement = select(model).where(_column(model, "supersedes_id") == id)
    return session.exec(statement).first()


def _column(model: type[V], name: str) -> Any:
    """Reach a mapped column off a protocol-bound model class, past the type checker."""
    return getattr(model, name)

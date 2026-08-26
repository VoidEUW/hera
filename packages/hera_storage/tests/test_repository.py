"""The generic repository, including its behaviour on models without SoftDeletable."""

from __future__ import annotations

from uuid import uuid4

import pytest
from models import Gadget, Trinket, Widget
from sqlmodel import Session

from hera_storage import Database, EntityStatus, NotFound, Repository, utcnow


def _widgets(session: Session) -> Repository[Widget]:
    return Repository(Widget, session)


def _gadgets(session: Session) -> Repository[Gadget]:
    return Repository(Gadget, session)


# -- reading -------------------------------------------------------------------


def test_add_returns_a_flushed_object(session: Session) -> None:
    repo = _widgets(session)
    widget = repo.add(Widget(name="one"))
    assert widget.id is not None
    assert repo.get(widget.id) is widget


def test_add_all(session: Session) -> None:
    repo = _widgets(session)
    added = repo.add_all([Widget(name="a"), Widget(name="b")])
    assert len(added) == 2
    assert repo.count() == 2


def test_get_returns_none_for_an_unknown_id(session: Session) -> None:
    assert _widgets(session).get(uuid4()) is None


def test_get_or_raise_carries_model_name_and_id(session: Session) -> None:
    missing = uuid4()
    with pytest.raises(NotFound) as excinfo:
        _widgets(session).get_or_raise(missing)

    assert excinfo.value.model_name == "Widget"
    assert excinfo.value.id == missing
    assert str(missing) in str(excinfo.value)


def test_list_filters_orders_and_paginates(session: Session) -> None:
    repo = _widgets(session)
    repo.add_all([Widget(name=f"w{i}", size=i) for i in range(5)])

    assert [w.size for w in repo.list(order_by=Widget.size)] == [0, 1, 2, 3, 4]
    assert [w.size for w in repo.list(order_by=Widget.size, limit=2)] == [0, 1]
    assert [w.size for w in repo.list(order_by=Widget.size, limit=2, offset=3)] == [3, 4]
    assert [w.size for w in repo.list(Widget.size > 2, order_by=Widget.size)] == [3, 4]
    assert [w.size for w in repo.list(Widget.size > 0, Widget.size < 3, order_by=Widget.size)] == [
        1,
        2,
    ]


def test_list_is_deterministic_without_an_explicit_order(session: Session) -> None:
    """Pagination correctness: an unordered query may reshuffle between calls.

    All six rows share a timestamp, so `created_at` alone would leave the order undefined
    and the second page could skip or repeat rows. The `id` tiebreaker settles it.
    """
    repo = _widgets(session)
    stamp = utcnow()
    repo.add_all([Widget(name=f"w{i}", size=i, created_at=stamp) for i in range(6)])

    expected = [w.id for w in repo.list()]
    assert expected == sorted(expected, key=str)
    assert [w.id for w in repo.list()] == expected

    pages = [[w.id for w in repo.list(limit=2, offset=start)] for start in (0, 2, 4)]
    assert pages[0] + pages[1] + pages[2] == expected
    assert len({page_id for page in pages for page_id in page}) == 6


def test_explicit_order_by_replaces_the_default(session: Session) -> None:
    repo = _widgets(session)
    stamp = utcnow()
    repo.add_all([Widget(name=f"w{i}", size=5 - i, created_at=stamp) for i in range(6)])

    assert [w.size for w in repo.list(order_by=Widget.size)] == [0, 1, 2, 3, 4, 5]


def test_models_without_entity_have_no_default_order(session: Session) -> None:
    """`Repository` is generic over SQLModel, so `created_at` may not exist at all."""
    repo: Repository[Trinket] = Repository(Trinket, session)
    repo.add_all([Trinket(name="a"), Trinket(name="b")])

    assert len(repo.list()) == 2
    assert [t.name for t in repo.list(order_by=Trinket.name)] == ["a", "b"]


def test_count_and_exists(session: Session) -> None:
    repo = _widgets(session)
    widget = repo.add(Widget(name="counted", size=7))

    assert repo.count() == 1
    assert repo.count(Widget.size == 7) == 1
    assert repo.count(Widget.size == 8) == 0
    assert repo.exists(widget.id) is True
    assert repo.exists(uuid4()) is False


# -- soft delete ---------------------------------------------------------------


def test_revoke_hides_the_row_and_stamps_revoked_at(session: Session) -> None:
    repo = _widgets(session)
    widget = repo.add(Widget(name="gone"))

    revoked = repo.revoke(widget.id)
    assert revoked.status is EntityStatus.REVOKED
    assert revoked.revoked_at is not None

    assert repo.get(widget.id) is None
    assert repo.get(widget.id, include_revoked=True) is not None
    assert repo.list() == []
    assert len(repo.list(include_revoked=True)) == 1
    assert repo.count() == 0
    assert repo.count(include_revoked=True) == 1
    assert repo.exists(widget.id) is False


def test_get_or_raise_treats_a_revoked_row_as_missing(session: Session) -> None:
    repo = _widgets(session)
    widget = repo.add(Widget(name="gone"))
    repo.revoke(widget.id)

    with pytest.raises(NotFound):
        repo.get_or_raise(widget.id)
    assert repo.get_or_raise(widget.id, include_revoked=True).id == widget.id


def test_restore_undoes_a_revoke(session: Session) -> None:
    repo = _widgets(session)
    widget = repo.add(Widget(name="back"))
    repo.revoke(widget.id)

    restored = repo.restore(widget.id)
    assert restored.status is EntityStatus.ACTIVE
    assert restored.revoked_at is None
    assert repo.get(widget.id) is not None


def test_revoke_raises_for_an_unknown_id(session: Session) -> None:
    with pytest.raises(NotFound):
        _widgets(session).revoke(uuid4())


# -- models without SoftDeletable ----------------------------------------------


def test_include_revoked_is_ignored_when_the_model_cannot_be_revoked(session: Session) -> None:
    """The parameter must be a no-op here, not an error."""
    repo = _gadgets(session)
    gadget = repo.add(Gadget(name="plain"))

    assert repo.get(gadget.id, include_revoked=False) is not None
    assert repo.get(gadget.id, include_revoked=True) is not None
    assert len(repo.list(include_revoked=False)) == 1
    assert len(repo.list(include_revoked=True)) == 1
    assert repo.count(include_revoked=False) == 1
    assert repo.get_or_raise(gadget.id, include_revoked=False).id == gadget.id
    assert repo.exists(gadget.id) is True


def test_revoke_and_restore_reject_a_model_without_soft_delete(session: Session) -> None:
    repo = _gadgets(session)
    gadget = repo.add(Gadget(name="plain"))

    with pytest.raises(TypeError, match="SoftDeletable"):
        repo.revoke(gadget.id)
    with pytest.raises(TypeError, match="SoftDeletable"):
        repo.restore(gadget.id)


# -- writing -------------------------------------------------------------------


def test_save_flushes_an_attached_instance(session: Session) -> None:
    repo = _widgets(session)
    widget = repo.add(Widget(name="original"))

    widget.name = "changed"
    saved = repo.save(widget)

    assert saved is widget
    assert repo.get(widget.id) is not None
    assert repo.list(Widget.name == "changed") != []


def test_save_merges_a_detached_instance(db: Database) -> None:
    """The FastAPI case: an object rebuilt from a payload, carrying an existing id."""
    with db.session() as session:
        widget_id = _widgets(session).add(Widget(name="stored")).id

    with db.session() as session:
        repo = _widgets(session)
        saved = repo.save(Widget(id=widget_id, name="rebuilt"))
        assert saved.name == "rebuilt"

    with db.session() as session:
        repo = _widgets(session)
        assert repo.count() == 1
        assert repo.get_or_raise(widget_id).name == "rebuilt"


def test_hard_delete_removes_the_row(session: Session) -> None:
    repo = _widgets(session)
    widget = repo.add(Widget(name="doomed"))

    repo.hard_delete(widget.id)
    assert repo.get(widget.id, include_revoked=True) is None
    assert repo.count(include_revoked=True) == 0


def test_hard_delete_works_on_a_revoked_row(session: Session) -> None:
    repo = _widgets(session)
    widget = repo.add(Widget(name="doomed"))
    repo.revoke(widget.id)

    repo.hard_delete(widget.id)
    assert repo.count(include_revoked=True) == 0


def test_hard_delete_raises_for_an_unknown_id(session: Session) -> None:
    with pytest.raises(NotFound):
        _widgets(session).hard_delete(uuid4())


def test_repository_writes_do_not_commit(db: Database) -> None:
    """Everything a repository does belongs to the surrounding unit of work."""
    with pytest.raises(RuntimeError), db.session() as session:
        _widgets(session).add(Widget(name="never-committed"))
        raise RuntimeError("abort")

    with db.session() as session:
        assert _widgets(session).count() == 0


# -- subclassing ---------------------------------------------------------------


class WidgetRepository(Repository[Widget]):
    """What a domain library writes, e.g. `class ChatRepository(Repository[Chat])`."""

    def __init__(self, session: Session) -> None:
        super().__init__(Widget, session)

    def larger_than(self, size: int) -> list[Widget]:
        return self.list(Widget.size > size, order_by=Widget.size)


def test_subclass_inherits_the_generic_behaviour(session: Session) -> None:
    repo = WidgetRepository(session)
    repo.add_all([Widget(name="s", size=1), Widget(name="l", size=9)])

    assert [w.size for w in repo.larger_than(5)] == [9]
    assert repo.count() == 2

    # The inherited soft-delete filter applies to the subclass's own queries too.
    revoked = repo.add(Widget(name="x", size=99))
    repo.revoke(revoked.id)
    assert [w.size for w in repo.larger_than(5)] == [9]

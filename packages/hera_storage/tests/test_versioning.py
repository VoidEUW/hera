"""Snapshot versioning across generations, plus the guards against a broken chain."""

from __future__ import annotations

from uuid import uuid4

from hera_storage.versioning import MAX_VERSION_CHAIN
from models import Widget
from sqlmodel import Session

from hera_storage import Repository, current_version, new_version, version_history


def test_new_version_copies_applies_changes_and_flips_the_flag(session: Session) -> None:
    first = Repository(Widget, session).add(Widget(name="v1", size=1))

    second = new_version(session, first, origin="manual", name="v2")

    assert second.id != first.id
    assert second.version == 2
    assert second.supersedes_id == first.id
    assert second.origin == "manual"
    assert second.is_current is True
    assert second.name == "v2"
    # Untouched fields ride along; it is a snapshot, not a diff.
    assert second.size == 1

    assert first.is_current is False
    assert first.version == 1
    assert first.name == "v1"


def test_three_generations_have_a_correct_history(session: Session) -> None:
    v1 = Repository(Widget, session).add(Widget(name="gen1", size=1))
    v2 = new_version(session, v1, origin="manual", name="gen2")
    v3 = new_version(session, v2, origin="dream:abc", name="gen3", size=3)

    history = version_history(session, Widget, v3.id)

    assert [w.id for w in history] == [v1.id, v2.id, v3.id]
    assert [w.version for w in history] == [1, 2, 3]
    assert [w.name for w in history] == ["gen1", "gen2", "gen3"]
    assert [w.is_current for w in history] == [False, False, True]
    assert [w.origin for w in history] == [None, "manual", "dream:abc"]
    assert [w.size for w in history] == [1, 1, 3]


def test_history_from_a_middle_version_stops_there(session: Session) -> None:
    """The walk goes backwards, so later versions are not part of the result."""
    v1 = Repository(Widget, session).add(Widget(name="gen1"))
    v2 = new_version(session, v1, origin="manual", name="gen2")
    new_version(session, v2, origin="manual", name="gen3")

    assert [w.version for w in version_history(session, Widget, v2.id)] == [1, 2]


def test_history_of_an_unversioned_row_is_just_itself(session: Session) -> None:
    widget = Repository(Widget, session).add(Widget(name="only"))
    assert [w.id for w in version_history(session, Widget, widget.id)] == [widget.id]


def test_history_of_an_unknown_id_is_empty(session: Session) -> None:
    assert version_history(session, Widget, uuid4()) == []


def test_current_version_walks_forward_from_any_version(session: Session) -> None:
    v1 = Repository(Widget, session).add(Widget(name="gen1"))
    v2 = new_version(session, v1, origin="manual", name="gen2")
    v3 = new_version(session, v2, origin="manual", name="gen3")

    for known in (v1, v2, v3):
        found = current_version(session, Widget, known.id)
        assert found is not None
        assert found.id == v3.id


def test_current_version_of_an_unknown_id_is_none(session: Session) -> None:
    assert current_version(session, Widget, uuid4()) is None


def test_current_version_does_not_depend_on_the_is_current_flag(session: Session) -> None:
    """A flag that was never cleared must not derail the walk."""
    v1 = Repository(Widget, session).add(Widget(name="gen1"))
    v2 = new_version(session, v1, origin="manual", name="gen2")
    v1.is_current = True
    session.flush()

    found = current_version(session, Widget, v1.id)
    assert found is not None
    assert found.id == v2.id


# -- broken chains -------------------------------------------------------------


def test_version_history_terminates_on_a_cycle(session: Session) -> None:
    """supersedes_id has no foreign key, so a cycle is possible and must not hang."""
    repo = Repository(Widget, session)
    a = repo.add(Widget(name="a"))
    b = repo.add(Widget(name="b"))
    a.supersedes_id = b.id
    b.supersedes_id = a.id
    session.flush()

    history = version_history(session, Widget, a.id)

    assert len(history) == 2
    assert {w.id for w in history} == {a.id, b.id}


def test_version_history_terminates_on_a_self_reference(session: Session) -> None:
    widget = Repository(Widget, session).add(Widget(name="self"))
    widget.supersedes_id = widget.id
    session.flush()

    assert [w.id for w in version_history(session, Widget, widget.id)] == [widget.id]


def test_current_version_terminates_on_a_cycle(session: Session) -> None:
    repo = Repository(Widget, session)
    a = repo.add(Widget(name="a"))
    b = repo.add(Widget(name="b"))
    a.supersedes_id = b.id
    b.supersedes_id = a.id
    session.flush()

    found = current_version(session, Widget, a.id)
    assert found is not None
    assert found.id in {a.id, b.id}


def test_the_chain_guard_is_bounded() -> None:
    assert MAX_VERSION_CHAIN > 0

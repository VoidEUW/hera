"""The mixins: combinability, metadata configuration and timestamp behaviour."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

from models import Doodad, Gadget, Gizmo, Widget
from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect
from sqlmodel import Session, SQLModel

from hera_storage import (
    NAMING_CONVENTION,
    Database,
    Entity,
    EntityStatus,
    SoftDeletable,
    UTCDateTime,
    Versioned,
    utcnow,
)


def _table(model: type[SQLModel]) -> Table:
    """SQLModel attaches __table__ to table=True classes; the type stubs don't say so."""
    return cast(Table, cast(Any, model).__table__)


def test_entity_status_values() -> None:
    assert EntityStatus.ACTIVE.value == "active"
    assert EntityStatus.REVOKED.value == "revoked"


def test_no_mixin_is_a_table() -> None:
    """The whole library must not contribute a single table."""
    for mixin in (Entity, SoftDeletable, Versioned):
        assert not hasattr(mixin, "__table__")

    library_tables = [
        name for name in SQLModel.metadata.tables if not name.startswith(("test_", "plugin_"))
    ]
    assert library_tables == []


def test_all_three_mixins_combine() -> None:
    """`class Foo(Entity, SoftDeletable, Versioned, table=True)` -- no MRO or field clash."""
    assert [cls.__name__ for cls in Widget.__mro__[:5]] == [
        "Widget",
        "Entity",
        "SoftDeletable",
        "Versioned",
        "SQLModel",
    ]
    assert set(_table(Widget).columns.keys()) == {
        "id",
        "created_at",
        "updated_at",
        "status",
        "revoked_at",
        "version",
        "supersedes_id",
        "origin",
        "is_current",
        "name",
        "size",
    }

    widget = Widget(name="combined")
    assert widget.id is not None
    assert widget.status is EntityStatus.ACTIVE
    assert widget.version == 1
    assert widget.is_current is True
    assert widget.supersedes_id is None
    assert widget.origin is None
    assert widget.revoked_at is None


def test_mixins_are_reusable_across_classes() -> None:
    """Two tables over the same mixins: only possible because no Column object is shared."""
    assert _table(Widget).c.status is not _table(Gizmo).c.status
    assert _table(Widget).c.created_at.table is _table(Widget)
    assert _table(Gizmo).c.created_at.table is _table(Gizmo)


def test_mixins_are_optional() -> None:
    assert not issubclass(Gadget, SoftDeletable)
    assert not issubclass(Gadget, Versioned)
    assert set(_table(Gadget).columns.keys()) == {"id", "created_at", "updated_at", "name"}


def test_naming_convention_is_applied_to_the_metadata() -> None:
    """SQLModel builds its MetaData at import time, so this assignment has to stick."""
    assert dict(SQLModel.metadata.naming_convention) == NAMING_CONVENTION


def test_generated_constraint_names_follow_the_convention() -> None:
    """The names themselves, not just the setting.

    Alembic's batch mode -- the only way to alter a column under SQLite -- needs every
    constraint to carry a deterministic name. A default `None` name only surfaces at the
    first migration, months later.
    """
    assert _table(Widget).primary_key.name == "pk_test_widgets"

    unique = [
        constraint
        for constraint in _table(Doodad).constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert [constraint.name for constraint in unique] == ["uq_test_doodads_code"]

    assert {index.name for index in _table(Doodad).indexes} == {
        "ix_test_doodads_bucket",
        "ix_test_doodads_created_at",
    }


def test_indexes_cover_the_columns_every_query_touches() -> None:
    indexes = {
        str(index.name): [column.name for column in index.columns]
        for index in _table(Widget).indexes
    }

    # Backs the default ordering of Repository.list, tiebreaker included.
    assert indexes["ix_test_widgets_created_at"] == ["created_at", "id"]
    # Backs the soft-delete filter and the current-version lookup.
    assert indexes["ix_test_widgets_status"] == ["status"]
    assert indexes["ix_test_widgets_is_current"] == ["is_current"]


def test_the_ordering_index_is_built_per_table() -> None:
    """A declared_attr, because one Index object cannot belong to two tables."""
    widget_index = next(i for i in _table(Widget).indexes if i.name == "ix_test_widgets_created_at")
    gizmo_index = next(i for i in _table(Gizmo).indexes if i.name == "ix_test_gizmos_created_at")
    assert widget_index is not gizmo_index


def test_updated_at_tracks_plain_attribute_assignment(db: Database) -> None:
    """No repository call, no manual stamping -- the column's onupdate does it."""
    with db.session() as session:
        widget = Widget(name="before")
        session.add(widget)
        session.flush()
        widget_id = widget.id
        first = widget.updated_at

    time.sleep(0.01)

    with db.session() as session:
        loaded = session.get(Widget, widget_id)
        assert loaded is not None
        loaded.name = "after"

    with db.session() as session:
        reloaded = session.get(Widget, widget_id)
        assert reloaded is not None
        # No tzinfo juggling needed any more -- both sides are aware UTC.
        assert reloaded.updated_at > first


def test_timestamps_stay_aware_utc_across_a_sqlite_roundtrip(db: Database) -> None:
    """UTCDateTime earns its keep here: SQLite stores no offset, so a plain
    DateTime(timezone=True) would hand back naive values from this query."""
    with db.session() as session:
        widget = Widget(name="tz")
        session.add(widget)
        session.flush()
        assert widget.created_at.tzinfo is not None
        widget_id = widget.id

    with db.session() as session:
        reloaded = session.get(Widget, widget_id)
        assert reloaded is not None
        assert reloaded.created_at.utcoffset() == timedelta(0)
        assert reloaded.updated_at.utcoffset() == timedelta(0)
        # The point of it all: comparing against an aware "now" must not raise.
        assert reloaded.created_at <= utcnow()


def test_naive_and_offset_inputs_are_normalised_to_utc(db: Database) -> None:
    naive = datetime(2026, 7, 28, 12, 0, 0)  # deliberately naive
    berlin = datetime(2026, 7, 28, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))

    with db.session() as session:
        assumed_utc = Widget(name="naive", created_at=naive)
        converted = Widget(name="offset", created_at=berlin)
        session.add_all([assumed_utc, converted])
        ids = (assumed_utc.id, converted.id)

    with db.session() as session:
        first = session.get(Widget, ids[0])
        second = session.get(Widget, ids[1])
        assert first is not None
        assert second is not None
        # A naive input is read as UTC, not as local time.
        assert first.created_at == datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
        # An offset input keeps its instant and arrives as UTC.
        assert second.created_at == datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def test_utcdatetime_handles_every_shape_it_can_be_handed() -> None:
    """Direct unit test: SQLite never returns an aware value, so the round-trip tests
    above cannot reach the branch that a PostgreSQL result would take."""
    decorator = UTCDateTime()
    dialect = sqlite_dialect()

    assert decorator.process_bind_param(None, dialect) is None
    assert decorator.process_result_value(None, dialect) is None

    naive = datetime(2026, 7, 28, 12, 0)  # deliberately naive
    assert decorator.process_result_value(naive, dialect) == datetime(
        2026, 7, 28, 12, 0, tzinfo=UTC
    )

    aware = datetime(2026, 7, 28, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    result = decorator.process_result_value(aware, dialect)
    assert result is not None
    assert result.utcoffset() == timedelta(0)
    assert result == datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def test_refresh_keeps_timestamps_aware(db: Database) -> None:
    """The reload path goes through UTCDateTime like any other read.

    Worth pinning separately: refresh() and the implicit reload after a commit bypass the
    ORM's identity map and are exactly where a missing result processor would show up.
    """
    with Session(db.engine) as session:
        widget = Widget(name="refresh")
        session.add(widget)
        session.commit()
        assert widget.updated_at.utcoffset() == timedelta(0)

        session.expire_all()
        session.refresh(widget)
        assert widget.updated_at.utcoffset() == timedelta(0)
        assert widget.created_at.utcoffset() == timedelta(0)


def test_status_round_trips_as_an_enum_not_a_string(db: Database) -> None:
    with db.session() as session:
        widget = Widget(name="enum")
        session.add(widget)
        session.flush()
        widget_id = widget.id

    with db.session() as session:
        reloaded = session.get(Widget, widget_id)
        assert reloaded is not None
        assert isinstance(reloaded.status, EntityStatus)

"""The profile row and its repository."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlmodel import Session

from hera_profiles import DEFAULT_SLUG, Profile, ProfileRepository, slugify


class TestSlugify:
    def test_it_lowercases_and_hyphenates(self) -> None:
        assert slugify("Coding Hera") == "coding-hera"

    def test_it_drops_everything_that_is_not_url_safe(self) -> None:
        assert slugify("Hera (v2) — für Code!") == "hera-v2-f-r-code"

    def test_it_never_returns_an_empty_string(self) -> None:
        """An empty slug would produce a route that cannot be addressed."""
        assert slugify("!!!") == "profile"
        assert slugify("   ") == "profile"


class TestCreating:
    def test_a_slug_is_derived_from_the_name(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        assert profiles.create(owner_id, "Coding Hera").slug == "coding-hera"

    def test_an_explicit_slug_wins(self, profiles: ProfileRepository, owner_id: UUID) -> None:
        assert profiles.create(owner_id, "Coding Hera", slug="code").slug == "code"

    def test_a_collision_gets_a_suffix_rather_than_an_error(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        """Two profiles called "Coding" is a thing a person does; refusing the second one
        teaches nothing."""
        assert profiles.create(owner_id, "Coding").slug == "coding"
        assert profiles.create(owner_id, "Coding").slug == "coding-2"
        assert profiles.create(owner_id, "Coding").slug == "coding-3"

    def test_two_owners_may_hold_the_same_slug(self, profiles: ProfileRepository) -> None:
        assert profiles.create(uuid4(), "Coding").slug == "coding"
        assert profiles.create(uuid4(), "Coding").slug == "coding"

    def test_extra_fields_are_forwarded(self, profiles: ProfileRepository, owner_id: UUID) -> None:
        created = profiles.create(owner_id, "Coding", pinned_skills=["writing"])
        assert created.pinned_skills == ["writing"]

    def test_the_defaults_are_empty_rather_than_absent(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        created = profiles.create(owner_id, "Coding")
        assert created.disabled_regions == []
        assert created.overrides == {}
        assert created.traits == {}
        assert created.renderer_format == "xml"


class TestScoping:
    def test_a_read_only_sees_its_own_owner(self, profiles: ProfileRepository) -> None:
        mine, theirs = uuid4(), uuid4()
        profiles.create(mine, "Mine")
        profiles.create(theirs, "Theirs")

        assert [p.name for p in profiles.for_owner(mine)] == ["Mine"]

    def test_by_slug_is_scoped_too(self, profiles: ProfileRepository) -> None:
        mine, theirs = uuid4(), uuid4()
        profiles.create(theirs, "Coding")
        assert profiles.by_slug(mine, "coding") is None
        assert profiles.by_slug(theirs, "coding") is not None

    def test_a_revoked_profile_disappears_from_reads(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        created = profiles.create(owner_id, "Old")
        profiles.revoke(created.id)
        assert profiles.for_owner(owner_id) == []


class TestTheDefaultProfile:
    def test_there_is_none_before_anything_exists(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        assert profiles.default_for(owner_id) is None

    def test_marking_one_unmarks_the_previous(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        first = profiles.make_default(profiles.create(owner_id, "First"))
        second = profiles.make_default(profiles.create(owner_id, "Second"))

        assert profiles.default_for(owner_id) is not None
        assert profiles.default_for(owner_id).id == second.id  # type: ignore[union-attr]
        assert not first.is_default

    def test_marking_does_not_reach_into_another_owner(self, profiles: ProfileRepository) -> None:
        mine, theirs = uuid4(), uuid4()
        hers = profiles.make_default(profiles.create(theirs, "Theirs"))
        profiles.make_default(profiles.create(mine, "Mine"))
        assert hers.is_default

    def test_an_unmarked_owner_falls_back_to_the_oldest(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        """An empty composer dropdown is worse than one showing a profile nobody picked."""
        oldest = profiles.create(owner_id, "First")
        profiles.create(owner_id, "Second")
        assert profiles.default_for(owner_id) is not None
        assert profiles.default_for(owner_id).id == oldest.id  # type: ignore[union-attr]

    def test_ensure_default_exists_creates_her_on_a_fresh_install(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        created = profiles.ensure_default_exists(owner_id)
        assert created.slug == DEFAULT_SLUG
        assert created.is_default

    def test_ensure_default_exists_is_idempotent(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        first = profiles.ensure_default_exists(owner_id)
        assert profiles.ensure_default_exists(owner_id).id == first.id
        assert len(profiles.for_owner(owner_id)) == 1

    def test_ensure_default_exists_adopts_a_profile_that_is_already_there(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        existing = profiles.create(owner_id, "Coding")
        assert profiles.ensure_default_exists(owner_id).id == existing.id


class TestJsonColumns:
    """SQLAlchemy cannot see an in-place edit to a JSON column on its own, and the usual
    ``sqlalchemy.ext.mutable`` wrapper is defeated by SQLModel's ``__setattr__``. The
    repository flags the four columns by name instead, so the obvious way to write the edit
    is also the correct one."""

    def test_an_in_place_edit_survives_a_save(
        self, profiles: ProfileRepository, session: Session, owner_id: UUID
    ) -> None:
        created = profiles.create(owner_id, "Coding")
        created.overrides["approach"] = "Write the test first."
        created.pinned_skills.append("writing")
        profiles.save(created)
        session.expire_all()

        reloaded = profiles.get_or_raise(created.id)
        assert reloaded.overrides == {"approach": "Write the test first."}
        assert reloaded.pinned_skills == ["writing"]

    def test_an_in_place_edit_without_a_save_is_lost(
        self, profiles: ProfileRepository, session: Session, owner_id: UUID
    ) -> None:
        """Documenting the trap rather than pretending it is gone: autoflush at commit does
        not rescue an unflagged JSON edit."""
        created = profiles.create(owner_id, "Coding")
        created.traits["identity.language"] = "German"
        session.flush()
        session.expire_all()

        assert profiles.get_or_raise(created.id).traits == {}

    def test_the_named_setters_do_not_need_a_save(
        self, profiles: ProfileRepository, session: Session, owner_id: UUID
    ) -> None:
        created = profiles.create(owner_id, "Coding")
        profiles.set_traits(created, {"identity.language": "German"})
        profiles.set_regions(created, disabled=["tone"], overrides={"role": "Reviewer."})
        profiles.set_pinned_skills(created, ["writing"])
        session.expire_all()

        reloaded = profiles.get_or_raise(created.id)
        assert reloaded.traits == {"identity.language": "German"}
        assert reloaded.disabled_regions == ["tone"]
        assert reloaded.overrides == {"role": "Reviewer."}
        assert reloaded.pinned_skills == ["writing"]

    def test_set_regions_leaves_alone_what_it_was_not_given(
        self, profiles: ProfileRepository, owner_id: UUID
    ) -> None:
        created = profiles.create(owner_id, "Coding", overrides={"role": "Reviewer."})
        profiles.set_regions(created, disabled=["tone"])
        assert created.overrides == {"role": "Reviewer."}

    def test_a_detached_profile_saves_without_flagging(
        self, profiles: ProfileRepository, session: Session, owner_id: UUID
    ) -> None:
        """merge() compares against a freshly loaded row and notices on its own."""
        created = profiles.create(owner_id, "Coding")
        profile_id = created.id
        session.expunge(created)

        created.traits = {"identity.language": "German"}
        profiles.save(created)
        session.expire_all()

        assert profiles.get_or_raise(profile_id).traits == {"identity.language": "German"}


class TestTheTable:
    def test_it_carries_the_package_prefix(self) -> None:
        """All models share one MetaData, so an unprefixed name from two packages would
        silently collide."""
        assert Profile.__tablename__ == "profile_profiles"

    def test_it_keeps_the_default_ordering_index(self) -> None:
        """Entity supplies this through a declared_attr, and a class-level __table_args__
        shadows it -- so the index has to be repeated by hand or `list()` loses its
        deterministic order."""
        table = Profile.metadata.tables["profile_profiles"]
        indexed = {tuple(column.name for column in index.columns) for index in table.indexes}
        assert ("created_at", "id") in indexed

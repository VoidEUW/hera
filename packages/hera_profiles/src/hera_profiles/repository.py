"""Data access for profiles.

Everything here is one session's worth of work. Nothing commits — that happens in
:meth:`hera_storage.Database.session`, so a profile change and whatever else the request did
land together or not at all.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, col

from hera_profiles.models import DEFAULT_SLUG, JSON_FIELDS, Profile
from hera_prompts import TraitValue
from hera_storage import Repository

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """A URL-safe handle for a profile name. Never empty."""
    slug = _SLUG_STRIP.sub("-", name.strip().lower()).strip("-")
    return slug or "profile"


class ProfileRepository(Repository[Profile]):
    """Profiles for one owner at a time.

    Every read takes an ``owner_id``. Single-user in v0.1, but the seam is load-bearing: a
    query that forgets the owner is the bug multi-user support is made of, and it is much
    easier to never write one than to find them all later.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(Profile, session)

    def for_owner(self, owner_id: UUID) -> list[Profile]:
        """Every active profile of one owner, oldest first."""
        return self.list(Profile.owner_id == owner_id)

    def by_slug(self, owner_id: UUID, slug: str) -> Profile | None:
        found = self.list(Profile.owner_id == owner_id, Profile.slug == slug, limit=1)
        return found[0] if found else None

    def default_for(self, owner_id: UUID) -> Profile | None:
        """The profile a new chat starts in.

        Falls back to the oldest profile when none is marked, rather than to ``None``: a
        composer with an empty dropdown is worse than a composer showing a profile the person
        did not choose, and the fallback is visible on screen either way.
        """
        # col() is SQLModel's escape hatch: the annotation says `bool`, the class attribute
        # is a column descriptor, and only col() tells a type checker which one it is.
        marked = self.list(Profile.owner_id == owner_id, col(Profile.is_default).is_(True), limit=1)
        if marked:
            return marked[0]
        existing = self.for_owner(owner_id)
        return existing[0] if existing else None

    def create(self, owner_id: UUID, name: str, *, slug: str = "", **fields: object) -> Profile:
        """Add a profile, giving it a slug that is free for this owner.

        Collisions get a numeric suffix instead of an error. Two profiles called "Coding" is
        a thing a person does, and refusing the second one teaches nothing.
        """
        profile = Profile(
            owner_id=owner_id,
            name=name,
            slug=self._free_slug(owner_id, slug or slugify(name)),
            **fields,  # forwarded straight into the model's own validation
        )
        return self.add(profile)

    def save(self, obj: Profile) -> Profile:
        """Persist a profile, including in-place edits to its JSON columns.

        SQLAlchemy cannot see ``profile.overrides["approach"] = ...`` — the attribute still
        holds the object it was loaded with, so the comparison finds no change and no UPDATE
        is issued. Flagging the four by name is the whole fix, and doing it here means the
        obvious way to write the edit is also the correct one. See
        :data:`hera_profiles.models.JSON_FIELDS` for why the usual wrapper does not work.

        Flagged only for an attached instance: a detached one goes through ``merge``, which
        compares against a freshly loaded row and notices the difference on its own.
        """
        if obj in self.session:
            for name in JSON_FIELDS:
                flag_modified(obj, name)
        return super().save(obj)

    def set_regions(
        self,
        profile: Profile,
        *,
        disabled: Sequence[str] | None = None,
        overrides: Mapping[str, str] | None = None,
    ) -> Profile:
        """Replace which regions this profile switches off and what they say instead."""
        if disabled is not None:
            profile.disabled_regions = list(disabled)
        if overrides is not None:
            profile.overrides = dict(overrides)
        return self.save(profile)

    def set_traits(self, profile: Profile, traits: Mapping[str, TraitValue]) -> Profile:
        """Replace this profile's behaviour traits.

        Not validated here. ``PromptBuilder`` drops what the registry will not admit and
        ``PromptBuilder.rejected_traits`` reports it, which keeps one answer to "is this
        value allowed" rather than two that can disagree.
        """
        profile.traits = dict(traits)
        return self.save(profile)

    def set_pinned_skills(self, profile: Profile, names: Sequence[str]) -> Profile:
        """Replace the skills this profile always carries."""
        profile.pinned_skills = list(names)
        return self.save(profile)

    def make_default(self, profile: Profile) -> Profile:
        """Mark one profile as the owner's default and unmark whatever held it.

        Enforced here rather than by a partial unique index, which SQLite and PostgreSQL spell
        differently. The cost is that a direct UPDATE outside this method can produce two
        defaults; :meth:`default_for` therefore takes the first rather than assuming one.
        """
        for other in self.for_owner(profile.owner_id):
            if other.is_default and other.id != profile.id:
                other.is_default = False
        profile.is_default = True
        return self.save(profile)

    def ensure_default_exists(self, owner_id: UUID) -> Profile:
        """The owner's default profile, created on first use if there is none.

        Called at boot. A fresh install has a mind and no rows, and the first turn should not
        be the thing that discovers that.
        """
        existing = self.default_for(owner_id)
        if existing is not None:
            return existing
        return self.make_default(
            self.create(
                owner_id,
                "Hera",
                slug=DEFAULT_SLUG,
                description="Her, as she is written in the mind.",
            )
        )

    def _free_slug(self, owner_id: UUID, wanted: str) -> str:
        if self.by_slug(owner_id, wanted) is None:
            return wanted
        suffix = 2
        while self.by_slug(owner_id, f"{wanted}-{suffix}") is not None:
            suffix += 1
        return f"{wanted}-{suffix}"

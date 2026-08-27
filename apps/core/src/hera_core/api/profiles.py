"""Profiles and the mind regions they select from.

Both live here because they are the same screen: a profile is a selection over regions, and
editing one without seeing the other is how you end up with a profile that overrides a region
that no longer says what you thought.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from hera_core.deps import Container, Db, Owner, not_found
from hera_core.schemas import ProfileOut, RegionIn, RegionOut
from hera_profiles import MIND_REGIONS, Profile, ProfileRepository, UnknownRegion, region

router = APIRouter(tags=["profiles"])


@router.get("/profiles", response_model=list[ProfileOut])
def list_profiles(owner: Owner, db: Db) -> list[ProfileOut]:
    """What the composer's dropdown shows. Not a model picker — there is one model (ADR 2),
    and there are many of her."""
    return [ProfileOut.of(profile) for profile in ProfileRepository(db).for_owner(owner)]


@router.post("/profiles/{profile_id}/default", response_model=ProfileOut)
def make_default(profile_id: UUID, owner: Owner, db: Db) -> ProfileOut:
    profiles = ProfileRepository(db)
    return ProfileOut.of(profiles.make_default(_require(db, profile_id, owner)))


@router.get("/mind", response_model=list[RegionOut])
def list_regions(container: Container) -> list[RegionOut]:
    """Every region, its current text, and how many times it has been written.

    The generation count is a git commit count rather than a column, which is the whole reason
    the mind is a repository: it cannot drift from the history, because it *is* the history.
    """
    texts = container.mind.read_all()
    return [
        RegionOut.of(
            item,
            text=texts.get(item.id, ""),
            generation=container.mind.generation(item.id),
        )
        for item in MIND_REGIONS
    ]


@router.put("/mind/{region_id}", response_model=RegionOut)
def write_region(region_id: str, payload: RegionIn, container: Container) -> RegionOut:
    """Edit a region. This is the owner's door, and it opens every one of them.

    Including the owner-fixed ones: editing ``safety`` here is the actual mechanism behind
    "add a rule without touching code". Dreaming uses a different door — ``propose`` — which
    refuses those, so a bug in a proposer cannot become a bug in her conduct.
    """
    try:
        item = region(region_id)
    except UnknownRegion as exc:
        raise not_found("mind region") from exc

    container.mind.write(region_id, payload.text)
    return RegionOut.of(
        item,
        text=container.mind.read(region_id),
        generation=container.mind.generation(region_id),
    )


@router.get("/mind/{region_id}/history", status_code=status.HTTP_200_OK)
def region_history(region_id: str, container: Container, limit: int = 50) -> list[dict[str, str]]:
    """Every commit that touched this region, newest first.

    Plain dictionaries rather than a schema: this is a git log, the fields are git's, and
    wrapping them in a model of ours would only be a place for the two to disagree.
    """
    try:
        region(region_id)
    except UnknownRegion as exc:
        raise not_found("mind region") from exc
    return [
        {
            "sha": version.sha,
            "when": version.when.isoformat(),
            "message": version.message,
            "origin": version.origin,
        }
        for version in container.mind.history(region_id, limit=limit)
    ]


def _require(db: Db, profile_id: UUID, owner: UUID) -> Profile:
    profile = ProfileRepository(db).get(profile_id)
    if profile is None or profile.owner_id != owner:
        raise not_found("profile")
    return profile

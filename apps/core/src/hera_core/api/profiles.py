"""Profiles and the mind regions they select from.

Both live here because they are the same screen: a profile is a selection over regions, and
editing one without seeing the other is how you end up with a profile that overrides a region
that no longer says what you thought.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from hera_core.auth import Viewer
from hera_core.deps import Container, Db, Owner, SignedIn, not_found
from hera_core.schemas import ProfileOut, RegionIn, RegionOut
from hera_core.wiring import Services
from hera_profiles import (
    MIND_REGIONS,
    SHARED_REGIONS,
    MindRepository,
    PersonalMind,
    Profile,
    ProfileRepository,
    UnknownRegion,
    region,
)

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


MindScope = Literal["mine", "template"]
"""Whose mind a request means: the signed-in person's own, or the template an admin edits — the
starting point for every new person, and where the shared regions live (ADR 28)."""


@router.get("/mind", response_model=list[RegionOut])
def list_regions(
    viewer: SignedIn, container: Container, scope: MindScope = "mine"
) -> list[RegionOut]:
    """Every region, its current text, and how many times it has been written.

    The generation count is a git commit count rather than a column, which is the whole reason
    the mind is a repository: it cannot drift from the history, because it *is* the history.
    """
    mind = _mind(container, viewer, scope)
    texts = mind.read_all()
    return [
        RegionOut.of(
            item,
            text=texts.get(item.id, ""),
            generation=mind.generation(item.id),
            shared=item.id in SHARED_REGIONS,
        )
        for item in MIND_REGIONS
    ]


@router.put("/mind/{region_id}", response_model=RegionOut)
def write_region(
    region_id: str,
    payload: RegionIn,
    viewer: SignedIn,
    container: Container,
    scope: MindScope = "mine",
) -> RegionOut:
    """Edit a region. This is the person's door, and it opens every region that is theirs.

    Including the owner-fixed ones that are about them, like ``about_you``. A **shared** region —
    ``safety``, ``tool_usage``, ``developer`` — is the instance's: an admin's edit lands in the
    template and is everybody's, and anybody else gets a 403. Dreaming uses a different door,
    ``propose``, which refuses owner-fixed and shared regions alike, so a bug in a proposer
    cannot become a bug in her conduct.
    """
    try:
        item = region(region_id)
    except UnknownRegion as exc:
        raise not_found("mind region") from exc

    shared = item.id in SHARED_REGIONS
    if shared or scope == "template":
        if not viewer.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="this region is the same for everybody here, and only an admin changes it",
            )
        container.mind.write(region_id, payload.text)
    else:
        _personal(container, viewer).write(region_id, payload.text)
    mind = _mind(container, viewer, scope)
    return RegionOut.of(
        item, text=mind.read(region_id), generation=mind.generation(region_id), shared=shared
    )


@router.get("/mind/{region_id}/history", status_code=status.HTTP_200_OK)
def region_history(
    region_id: str,
    viewer: SignedIn,
    container: Container,
    limit: int = 50,
    scope: MindScope = "mine",
) -> list[dict[str, str]]:
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
        for version in _mind(container, viewer, scope).history(region_id, limit=limit)
    ]


def _personal(container: Services, viewer: Viewer) -> PersonalMind:
    return container.for_user(viewer.id).mind


def _mind(container: Services, viewer: Viewer, scope: MindScope) -> MindRepository | PersonalMind:
    """The mind a request means. The template is an admin's to read as well as to write: it is
    the instance's, and what it says is not a person's business until it is in their own."""
    if scope == "template":
        if not viewer.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="only an admin edits the template"
            )
        return container.mind
    return _personal(container, viewer)


def _require(db: Db, profile_id: UUID, owner: UUID) -> Profile:
    profile = ProfileRepository(db).get(profile_id)
    if profile is None or profile.owner_id != owner:
        raise not_found("profile")
    return profile

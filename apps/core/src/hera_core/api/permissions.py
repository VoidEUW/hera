"""What she may do without asking: the rules, and a way to make, change and remove them (#109).

Rules are identified by their **pattern** — one rule per pattern, and the pattern is not
editable, because a different pattern is a different rule — which is why the pattern is the path
and everything else is the body. The operations live in :mod:`hera_core.rulebook`, shared with
"always" on a confirmation card, so the screen and the card cannot disagree about what survives
a restart.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status

from hera_core import rulebook
from hera_core.deps import AdminOnly, Container
from hera_core.schemas import (
    FallbackPatch,
    MatchesOut,
    PermissionsOut,
    RuleIn,
    RuleOut,
    RulePatch,
)
from hera_permissions import InvalidPattern

router = APIRouter(tags=["permissions"])


@router.get("/permissions", response_model=PermissionsOut)
async def read_permissions(container: Container) -> PermissionsOut:
    """Allow, deny and ask, with each rule's name, where it came from, and the tools it covers.

    Sorted by pattern rather than left in the order they were added: the set is unordered by
    design — rules resolve by specificity, not position — and showing them in insertion order
    would suggest an authority the pattern does not have.
    """
    known = await _known_tools(container)
    return PermissionsOut(
        fallback=rulebook.fallback(container).value,
        rules=[
            RuleOut(
                pattern=view.pattern,
                decision=view.decision.value,
                reason=view.reason,
                profile=view.profile,
                name=view.name,
                source=view.source,
                covers=rulebook.matching(view.pattern, known),
            )
            for view in rulebook.rules(container)
        ],
    )


@router.post(
    "/permissions/rules",
    response_model=RuleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminOnly],
)
async def create_rule(payload: RuleIn, container: Container) -> RuleOut:
    try:
        view = rulebook.add(
            container,
            pattern=payload.pattern,
            decision=payload.decision,
            name=payload.name,
            reason=payload.reason,
        )
    except InvalidPattern as cause:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(cause)) from cause
    except rulebook.RuleExists as cause:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"there is already a rule on {cause}; change that one instead",
        ) from cause
    except rulebook.NoToolLayer as cause:
        raise _no_tool_layer() from cause
    return await _out(view, container)


@router.patch("/permissions/rules/{pattern:path}", response_model=RuleOut, dependencies=[AdminOnly])
async def change_rule(pattern: str, payload: RulePatch, container: Container) -> RuleOut:
    try:
        view = rulebook.change(
            container,
            pattern,
            name=payload.name,
            decision=payload.decision,
            reason=payload.reason,
        )
    except rulebook.NoSuchRule as cause:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such rule") from cause
    except rulebook.NoToolLayer as cause:
        raise _no_tool_layer() from cause
    return await _out(view, container)


@router.delete(
    "/permissions/rules/{pattern:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminOnly],
)
def delete_rule(pattern: str, container: Container) -> Response:
    try:
        rulebook.remove(container, pattern)
    except rulebook.NoSuchRule as cause:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such rule") from cause
    except rulebook.BuiltInRule as cause:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="that rule ships with Hera: change what it decides instead of removing it",
        ) from cause
    except rulebook.NoToolLayer as cause:
        raise _no_tool_layer() from cause
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/permissions", response_model=PermissionsOut, dependencies=[AdminOnly])
async def change_fallback(payload: FallbackPatch, container: Container) -> PermissionsOut:
    """What a tool no rule covers gets."""
    try:
        rulebook.set_fallback(container, payload.fallback)
    except rulebook.NoToolLayer as cause:
        raise _no_tool_layer() from cause
    return await read_permissions(container)


@router.get("/permissions/matches", response_model=MatchesOut)
async def matches(container: Container, pattern: str = Query(min_length=1)) -> MatchesOut:
    """Which of her tools a pattern would cover — asked by the new-rule form as it is typed, so
    the matcher is the one the policy uses and the browser holds no second copy of it."""
    return MatchesOut(
        pattern=pattern, tools=rulebook.matching(pattern, await _known_tools(container))
    )


async def _known_tools(container: Container) -> list[str]:
    if container.registry is None:
        return []
    return sorted(tool.name for tool in (await container.registry.catalogue()).tools)


async def _out(view: rulebook.RuleView, container: Container) -> RuleOut:
    return RuleOut(
        pattern=view.pattern,
        decision=view.decision.value,
        reason=view.reason,
        name=view.name,
        source=view.source,
        covers=rulebook.matching(view.pattern, await _known_tools(container)),
    )


def _no_tool_layer() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, detail="nothing is asking permissions in this deployment"
    )

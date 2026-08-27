"""The settings modal's three lists, and one health check.

Skills, servers and permissions are all *renderings of state the libraries already report*.
``ToolRegistry.status()`` returns exactly the four fields a server row shows, and the skill
loader already produces the problems a broken skill row explains — so nothing here computes
anything, which is the property to keep. A settings screen that derives its own view of whether
a server is connected is a settings screen that can be wrong.
"""

from __future__ import annotations

from fastapi import APIRouter

from hera_core import __version__
from hera_core.deps import Container, Db, Owner
from hera_core.schemas import (
    BrokenSkillOut,
    HealthOut,
    PermissionsOut,
    RuleOut,
    ServerOut,
    SkillOut,
    SkillsOut,
)
from hera_home import home
from hera_permissions import Rule
from hera_providers import ProviderSettings
from hera_skillsets import SkillUsageRepository

router = APIRouter(tags=["system"])


@router.get("/skills", response_model=SkillsOut)
def list_skills(owner: Owner, db: Db, container: Container) -> SkillsOut:
    """Every skill, with its usage counts and whatever is wrong with it.

    Broken ones are listed rather than omitted. A skill that vanished silently is
    indistinguishable from one never installed, and "why is my skill not being used" is the
    question this screen exists to answer.
    """
    usage = SkillUsageRepository(db).for_owner(owner)
    catalogue = container.library.catalogue()
    return SkillsOut(
        skills=[SkillOut.of(skill, usage.get(skill.id)) for skill in catalogue.skills],
        broken=[BrokenSkillOut.of(broken) for broken in catalogue.broken],
    )


@router.get("/servers", response_model=list[ServerOut])
async def list_servers(container: Container) -> list[ServerOut]:
    """One row per MCP server, with its failure reason when it has one."""
    if container.registry is None:
        return []
    return [
        ServerOut(
            name=status.name,
            connected=status.connected,
            tools=status.tools,
            failure=status.failure,
        )
        for status in await container.registry.status()
    ]


@router.get("/permissions", response_model=PermissionsOut)
def read_permissions(container: Container) -> PermissionsOut:
    """Allow, deny and ask, with the rules that came from a confirmation card marked as such.

    Sorted by pattern rather than left in the order they were added: the set is unordered by
    design — rules resolve by specificity, not position — and showing them in insertion order
    would suggest an authority the pattern does not have.
    """
    if container.registry is None:
        return PermissionsOut(fallback="ask", rules=[])
    policy = container.registry.policy
    rules = [_rule(rule) for rule in policy.base.rules]
    for name, permission_set in policy.profiles.items():
        rules.extend(_rule(rule, profile=name) for rule in permission_set.rules)
    return PermissionsOut(
        fallback=policy.fallback.value,
        rules=sorted(rules, key=lambda item: (item.pattern, item.profile or "")),
    )


@router.get("/health", response_model=HealthOut)
async def health(container: Container) -> HealthOut:
    """Everything a person needs to answer "is it wired up".

    One request, because the three things that are usually wrong on a fresh install — no
    skills found, no servers connected, the wrong model name — are wrong together and are much
    easier to see side by side.
    """
    servers = await list_servers(container)
    return HealthOut(
        ok=True,
        version=__version__,
        home=str(home()),
        model=ProviderSettings().model,
        skills=len(container.library.catalogue()),
        servers=servers,
    )


def _rule(rule: Rule, *, profile: str | None = None) -> RuleOut:
    return RuleOut(
        pattern=rule.pattern,
        decision=rule.decision.value,
        reason=rule.reason,
        profile=profile,
    )

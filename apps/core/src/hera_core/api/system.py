"""The settings modal's three lists, and one health check.

Skills, servers and permissions are all *renderings of state the libraries already report*.
``ToolRegistry.status()`` returns exactly the four fields a server row shows, and the skill
loader already produces the problems a broken skill row explains — so nothing here computes
anything, which is the property to keep. A settings screen that derives its own view of whether
a server is connected is a settings screen that can be wrong.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from hera_core import __version__, trust
from hera_core.clock import is_known
from hera_core.clock import render as render_now
from hera_core.config import load as load_config
from hera_core.config import save as save_config
from hera_core.deps import Container, Db, Owner
from hera_core.schemas import (
    BrokenSkillOut,
    HealthOut,
    PermissionsOut,
    PreferencesOut,
    PreferencesPatch,
    RuleOut,
    ServerOut,
    SkillIn,
    SkillOut,
    SkillsOut,
)
from hera_home import home
from hera_mcp import BUILTIN_SERVER_NAME
from hera_permissions import Rule
from hera_skillsets import SkillUsageRepository

router = APIRouter(tags=["system"])

DRAFT_BODY = """Write the instructions here.

A skill is read by the model when it is selected, so write it *to her*: what to do, in what
order, and what to avoid. Markdown, as long as it needs to be.
"""
"""What a new skill starts as. Not empty: an empty body is a skill the loader reports as having
nothing to inject, and a person's first skill should not open as an error."""


@router.get("/skills", response_model=SkillsOut)
def list_skills(owner: Owner, db: Db, container: Container) -> SkillsOut:
    """Every skill, with its usage counts, its provenance and whatever is wrong with it.

    Broken ones are listed rather than omitted. A skill that vanished silently is
    indistinguishable from one never installed, and "why is my skill not being used" is the
    question this screen exists to answer.
    """
    usage = SkillUsageRepository(db).for_owner(owner)
    catalogue = container.library.catalogue()

    problem = ""
    try:
        trusted = trust.load()
    except trust.TrustError as exc:
        # The list of skills is the point of this screen; the marks on it are not. A typo in
        # trusted.json costs the marks and says so.
        trusted, problem = trust.EMPTY, str(exc)

    return SkillsOut(
        skills=[
            SkillOut.of(skill, usage.get(skill.id), trust=trusted.skill(skill.id, skill.digest))
            for skill in catalogue.skills
        ],
        broken=[BrokenSkillOut.of(broken) for broken in catalogue.broken],
        trust_problem=problem,
    )


@router.post("/skills", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
def create_skill(payload: SkillIn, container: Container) -> SkillOut:
    """Write a new skill folder, so one can be started without leaving the interface.

    **The writing lives here, not in `hera_skillsets`.** That package reads the skills
    directory and says explicitly that it does not write to it — a library that both discovers
    content and creates it ends up owning a format it was only supposed to read. So this route
    lays out the same `SKILL.md` a person would write by hand, and the library discovers it on
    the next listing exactly as it discovers everything else.

    Deliberately minimal: an id, a description and a body. Author, licence, an icon and the
    rest are frontmatter you add in the file, which is the whole point of a skill being a
    folder you can open.
    """
    # `container.library.path`, not `skills_dir()`: the library is the thing that will have to
    # find this, and asking it where it looks means one answer rather than two that agree until
    # somebody points a deployment somewhere else.
    directory = container.library.path / payload.id
    if directory.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"there is already a skill folder called {payload.id!r}",
        )

    description = " ".join(payload.description.split())
    body = payload.body.strip() or DRAFT_BODY
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {payload.id}\ndescription: {description!r}\n---\n\n{body}\n",
        encoding="utf-8",
    )

    # Read back rather than reported from the request: what the screen shows is what the
    # loader made of the file, including any problem it has with it.
    written = container.library.get(payload.id)
    if written is None:  # pragma: no cover - the loader just wrote it
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="not saved")
    return SkillOut.of(written)


@router.get("/servers", response_model=list[ServerOut])
async def list_servers(container: Container) -> list[ServerOut]:
    """One row per MCP server, with its failure reason when it has one.

    Her own in-process server is not one of these: "servers" to a person means the
    ``mcp.json`` entries they added, and counting the builtin makes the composer say
    "1 server" on a machine with none. The row disappears here rather than in the
    interface because the health card reads the same list.
    """
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
        if status.name != BUILTIN_SERVER_NAME
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


@router.get("/preferences", response_model=PreferencesOut)
def read_preferences() -> PreferencesOut:
    return _preferences()


@router.patch("/preferences", response_model=PreferencesOut)
def write_preferences(payload: PreferencesPatch) -> PreferencesOut:
    """Change what is about *you* rather than about how she works.

    A bad zone is refused here rather than degraded, which is the opposite of what
    :func:`hera_core.clock.render` does with the same value — deliberately. A person typing into
    a settings screen should be told immediately; a turn that has already started should not
    fail over something somebody edited into a file last week.
    """
    if payload.timezone is not None:
        if not is_known(payload.timezone):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{payload.timezone!r} is not a time zone this system knows about",
            )
        save_config(load_config().with_timezone(payload.timezone))
    return _preferences()


def _preferences() -> PreferencesOut:
    config = load_config()
    return PreferencesOut(timezone=config.timezone, now=render_now(config.timezone))


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
        model=container.model,
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

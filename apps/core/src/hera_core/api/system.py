"""The settings modal's three lists, and one health check.

Skills, servers and permissions are all *renderings of state the libraries already report*.
``ToolRegistry.status()`` returns exactly the four fields a server row shows, and the skill
loader already produces the problems a broken skill row explains — so nothing here computes
anything, which is the property to keep. A settings screen that derives its own view of whether
a server is connected is a settings screen that can be wrong.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from hera_core import __version__, emotions, trust
from hera_core.deps import Container, Db, Owner
from hera_core.schemas import (
    BrokenSkillOut,
    EmotionOut,
    EmotionsIn,
    EmotionsOut,
    HealthOut,
    PermissionsOut,
    RuleOut,
    ServerOut,
    SkillIn,
    SkillOut,
    SkillsOut,
)
from hera_home import home
from hera_mcp import DEFAULT_EMOTIONS
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


@router.get("/emotions", response_model=EmotionsOut)
def list_emotions() -> EmotionsOut:
    """Her stance vocabulary: what she can show, and what each one means.

    The same list the prompt is built from and the same list the interface colours a card
    with, which is the whole reason it is data rather than a paragraph in a mind region.
    """
    return _emotions()


@router.put("/emotions", response_model=EmotionsOut)
def write_emotions(payload: EmotionsIn) -> EmotionsOut:
    """Replace the vocabulary. Takes effect on the next turn — the list travels in the prompt,
    not in the tool description, precisely so that no restart is involved."""
    emotions.save(list(payload.emotions))
    return _emotions()


@router.post("/emotions/reset", response_model=EmotionsOut)
def reset_emotions() -> EmotionsOut:
    """Put the shipped vocabulary back."""
    emotions.reset()
    return _emotions()


def _emotions() -> EmotionsOut:
    problem = ""
    try:
        found = emotions.load()
    except emotions.EmotionsError as exc:
        # The defaults are a working vocabulary; a broken file costs the customisation and
        # says so, rather than leaving the screen empty and her with nothing to show.
        found, problem = list(DEFAULT_EMOTIONS), str(exc)
    return EmotionsOut(
        emotions=[EmotionOut.of(emotion) for emotion in found],
        customised=emotions.emotions_path().is_file() and not problem,
        problem=problem,
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

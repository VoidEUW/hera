"""What the API sends and accepts.

Deliberately its own models rather than the table classes. Three reasons, and all three have
bitten this project's predecessor:

A table is a storage shape. Serialising `Profile` directly would put ``status``, ``revoked_at``
and ``updated_at`` into a public contract and make every schema change a breaking API change.

The browser's types are **generated from this** (ADR 6), so these names are the ones a Svelte
component reads. They should be named for what the interface calls them, not for what the
column is called.

And ``events`` crosses unchanged. A message's event list is dumped ``ChatEvent`` JSON and is
passed through as-is — the one place the API deliberately does not re-shape anything, because
the browser renders one component per variant and any translation here would be a second thing
to keep in step with the union.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from hera_chats import Chat, Message, Project
from hera_profiles import MindRegion, Profile
from hera_skillsets import BrokenSkill, Skill, SkillUsage


class ProfileOut(BaseModel):
    """One of her, as the composer's dropdown and the settings screen see her."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    slug: str
    name: str
    description: str
    is_default: bool
    disabled_regions: list[str]
    overrides: dict[str, str]
    traits: dict[str, bool | str | int]
    pinned_skills: list[str]

    @classmethod
    def of(cls, profile: Profile) -> ProfileOut:
        return cls(
            id=profile.id,
            slug=profile.slug,
            name=profile.name,
            description=profile.description,
            is_default=profile.is_default,
            disabled_regions=list(profile.disabled_regions),
            overrides=dict(profile.overrides),
            traits=dict(profile.traits),
            pinned_skills=list(profile.pinned_skills),
        )


class ProjectOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    slug: str
    name: str
    instructions: str
    pinned_skills: list[str]
    default_profile_id: UUID | None
    archived: bool

    @classmethod
    def of(cls, project: Project) -> ProjectOut:
        return cls(
            id=project.id,
            slug=project.slug,
            name=project.name,
            instructions=project.instructions,
            pinned_skills=list(project.pinned_skills),
            default_profile_id=project.default_profile_id,
            archived=project.archived,
        )


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    instructions: str = ""
    pinned_skills: list[str] = Field(default_factory=list)
    default_profile_id: UUID | None = None


class ProjectPatch(BaseModel):
    """Every field optional. ``None`` means "leave it", which is why nothing here has a
    meaningful ``None`` value of its own."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    instructions: str | None = None
    pinned_skills: list[str] | None = None
    default_profile_id: UUID | None = None
    archived: bool | None = None


class ChatOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    title: str
    project_id: UUID | None
    profile_id: UUID | None
    pinned: bool
    created_at: datetime
    last_message_at: datetime | None

    @classmethod
    def of(cls, chat: Chat) -> ChatOut:
        return cls(
            id=chat.id,
            title=chat.title,
            project_id=chat.project_id,
            profile_id=chat.profile_id,
            pinned=chat.pinned,
            created_at=chat.created_at,
            last_message_at=chat.last_message_at,
        )


class ChatIn(BaseModel):
    title: str = ""
    project_id: UUID | None = None
    profile_id: UUID | None = None


class MessageOut(BaseModel):
    """One message, with its event list exactly as stored.

    ``events`` is `list[dict]` rather than a typed union on purpose: it is dumped `ChatEvent`
    JSON, the browser discriminates on ``type``, and re-validating it here would only add a
    place where an event stored by a newer version fails to load in an older one.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    role: str
    content: str
    sequence: int
    created_at: datetime
    events: list[dict[str, Any]]

    @classmethod
    def of(cls, message: Message) -> MessageOut:
        return cls(
            id=message.id,
            role=message.role,
            content=message.content,
            sequence=message.sequence,
            created_at=message.created_at,
            events=list(message.events),
        )


class ChatDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    chat: ChatOut
    messages: list[MessageOut]


class MessageIn(BaseModel):
    text: str = Field(min_length=1)
    """What the person typed, ``/commands`` included — the router strips them server-side, so
    the browser must not."""


class PermissionAnswer(BaseModel):
    """The answer to a permission card."""

    call_ids: list[str] = Field(min_length=1)
    allow: bool
    remember: bool = False
    """Whether to write a rule. **Always allow** has to be visibly different from **Allow
    once** afterwards, or nobody can tell whether the decision stuck."""


class RegionOut(BaseModel):
    """One mind region, with its text and its history depth."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    purpose: str
    tier: str
    text: str
    generation: int
    """How many times it has been written. A commit count, not a column."""

    @classmethod
    def of(cls, region: MindRegion, *, text: str, generation: int) -> RegionOut:
        return cls(
            id=region.id,
            title=region.title,
            purpose=region.purpose,
            tier=region.tier.value,
            text=text,
            generation=generation,
        )


class RegionIn(BaseModel):
    text: str


class SkillOut(BaseModel):
    """A skill row on the settings screen."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str
    path: str
    resources: list[str]
    problems: list[str]
    hits: int = 0
    last_used_at: datetime | None = None

    @classmethod
    def of(cls, skill: Skill, usage: SkillUsage | None = None) -> SkillOut:
        return cls(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            path=str(skill.path),
            resources=list(skill.resources),
            problems=list(skill.problems),
            hits=usage.hits if usage is not None else 0,
            last_used_at=usage.last_used_at if usage is not None else None,
        )


class BrokenSkillOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    path: str
    reason: str

    @classmethod
    def of(cls, broken: BrokenSkill) -> BrokenSkillOut:
        return cls(id=broken.id, path=str(broken.path), reason=broken.reason)


class SkillsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    skills: list[SkillOut]
    broken: list[BrokenSkillOut]


class ServerOut(BaseModel):
    """One MCP server row, with its failure reason when it has one."""

    model_config = ConfigDict(frozen=True)

    name: str
    connected: bool
    tools: int
    failure: str | None = None


class RuleOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    pattern: str
    decision: str
    reason: str = ""
    profile: str | None = None


class PermissionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    fallback: str
    rules: list[RuleOut]


class HealthOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    version: str
    home: str
    model: str
    skills: int
    servers: list[ServerOut]

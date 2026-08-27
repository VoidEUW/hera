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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hera_chats import Chat, Message, Project
from hera_core.config import validate_provider_name
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

    attachments: list[AttachmentSummary] = Field(default_factory=list)
    """The files sent with it, **without their contents**.

    A chip in the interface needs a name and a size; sending the text back would put a
    megabyte of source into every chat load to render two words.
    """

    @classmethod
    def of(cls, message: Message) -> MessageOut:
        return cls(
            id=message.id,
            role=message.role,
            content=message.content,
            sequence=message.sequence,
            created_at=message.created_at,
            events=list(message.events),
            attachments=[
                AttachmentSummary(
                    name=str(item.get("name", "")), bytes=int(item.get("bytes", 0) or 0)
                )
                for item in message.attachments
            ],
        )


class AttachmentSummary(BaseModel):
    """A file's name and size. Never its contents — see :class:`MessageOut`."""

    model_config = ConfigDict(frozen=True)

    name: str
    bytes: int


class ChatDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    chat: ChatOut
    messages: list[MessageOut]


class AttachmentIn(BaseModel):
    """A file sent with a message, read in the browser.

    There is no upload endpoint, and that is deliberate rather than unfinished: a *project's*
    files need embeddings and retrieval and are v0.2, while a file attached to one question is
    context for that turn and nothing else.
    """

    name: str = Field(min_length=1, max_length=255)
    text: str
    bytes: int = 0


class MessageIn(BaseModel):
    text: str = ""
    """What the person typed, ``/commands`` included — the router strips them server-side, so
    the browser must not."""

    attachments: list[AttachmentIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _says_something(self) -> MessageIn:
        """A message has to carry *something*. A file on its own is a fair question."""
        if not self.text.strip() and not self.attachments:
            raise ValueError("a message needs text, a file, or both")
        return self


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


class ProviderOut(BaseModel):
    """One registered endpoint. Never carries the key — see ``api_key_set``."""

    model_config = ConfigDict(frozen=True)

    name: str
    base_url: str
    model: str
    embedding_model: str
    timeout_s: float
    connect_timeout_s: float
    api_key_set: bool


class ProvidersOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    providers: list[ProviderOut]
    active: str


class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    """Validated with the same function the stored entry uses, so a bad name is a 422 that
    says what a name may contain rather than a 500 from inside the handler."""

    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)
    api_key: str = ""
    embedding_model: str = ""
    timeout_s: float = 180.0
    connect_timeout_s: float = 5.0

    @field_validator("name")
    @classmethod
    def _usable_name(cls, name: str) -> str:
        return validate_provider_name(name)


class ProviderPatch(BaseModel):
    """Every field optional. ``None`` means "leave it".

    That is why ``api_key`` is ``str | None`` rather than ``str``: left out it keeps the key
    already on disk, and sent as ``""`` it clears it. A screen that never receives the key
    cannot otherwise preserve one.
    """

    base_url: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    api_key: str | None = None
    embedding_model: str | None = None
    timeout_s: float | None = None
    connect_timeout_s: float | None = None


class ProbeOut(BaseModel):
    """What an endpoint answered when asked for its models.

    A failure is a normal answer here, not an error status: "nothing is listening on that port"
    is the commonest thing to be wrong on a fresh install and belongs on the screen you were
    already looking at.
    """

    model_config = ConfigDict(frozen=True)

    ok: bool
    models: list[str]
    error: str


class HealthOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    version: str
    home: str
    model: str
    skills: int
    servers: list[ServerOut]

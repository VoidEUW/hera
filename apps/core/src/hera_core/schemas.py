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

from hera_skillsets.models import ID_PATTERN
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hera_chats import Chat, Message, Project
from hera_core.config import validate_provider_name
from hera_mcp import Emotion
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
    default_agent_id: UUID | None
    color: str
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
            default_agent_id=project.default_agent_id,
            color=project.color or "",
            archived=project.archived,
        )


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    instructions: str = ""
    pinned_skills: list[str] = Field(default_factory=list)
    default_profile_id: UUID | None = None
    color: str = Field(default="", max_length=32)


class ProjectPatch(BaseModel):
    """Every field optional. ``None`` means "leave it", which is why nothing here has a
    meaningful ``None`` value of its own.

    ``default_profile_id`` is the exception and it is handled at the route rather than here: a
    project *can* stop naming a default, so the route reads ``model_fields_set`` instead of
    testing for ``None``. See :func:`hera_core.api.projects.update_project`.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    instructions: str | None = None
    pinned_skills: list[str] | None = None
    default_profile_id: UUID | None = None
    color: str | None = Field(default=None, max_length=32)
    archived: bool | None = None

    # `default_agent_id` is deliberately not here. It is reported on `ProjectOut` so the screen
    # can show the control filled in, and there is nothing to fill it with until agents exist —
    # a writable field pointing at a concept with no rows would only let a client store a UUID
    # that resolves to nothing, which is worse than the control being disabled.


class ChatOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    title: str
    project_id: UUID | None
    profile_id: UUID | None
    pinned: bool
    pinned_skills: list[str]
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
            pinned_skills=list(chat.pinned_skills or []),
            created_at=chat.created_at,
            last_message_at=chat.last_message_at,
        )


class ChatIn(BaseModel):
    title: str = ""
    project_id: UUID | None = None
    profile_id: UUID | None = None


class ChatPatch(BaseModel):
    """Renaming, re-pinning, and moving. ``None`` means "leave it", as everywhere else here.

    A title typed by hand sticks: :meth:`hera_chats.ChatRepository.touch` only ever names a
    chat that has no name, so the next turn will not quietly rename it back. Clearing it to
    ``""`` therefore hands naming back to her.
    """

    title: str | None = Field(default=None, max_length=200)

    pinned_skills: list[str] | None = Field(default=None, max_length=32)
    """Skills switched on for this conversation. The whole list, because it is a set of
    toggles and three endpoints for add, remove and reorder would each have an opinion about
    an order the person can see."""

    project_id: UUID | None = None
    """Which project this chat lives in. **``None`` does not mean "leave it" here** — it means
    *loose*, which is a move a person makes deliberately and the only way back out of a project.

    That breaks this module's convention, so the route does not test for ``None``: it asks
    ``"project_id" in payload.model_fields_set`` and only touches the column when the field was
    actually sent. The alternative — a sentinel string, or a second endpoint for *remove from
    project* — would put the tri-state in the wire format, where every client has to know about
    it, instead of in the one route that cares.
    """


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
                    name=str(item.get("name", "")),
                    bytes=int(item.get("bytes", 0) or 0),
                    media_type=str(item.get("media_type", "") or ""),
                )
                for item in message.attachments
            ],
        )


class AttachmentSummary(BaseModel):
    """A file's name, size and kind. Never its contents — see :class:`MessageOut`."""

    model_config = ConfigDict(frozen=True)

    name: str
    bytes: int

    media_type: str = ""
    """``image/png`` for a picture, empty for text. Enough for the chip to say which it was
    without the browser guessing from the extension, and far short of sending the bytes back."""


class ChatDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    chat: ChatOut
    messages: list[MessageOut]


MAX_TEXT_CHARS = 4 * 1024 * 1024
"""A text attachment's ceiling. The browser stops far below this; the number here exists so a
request built by hand cannot put an arbitrary amount of memory into a JSON column."""

MAX_DATA_URL_CHARS = 32 * 1024 * 1024
"""A picture's ceiling, in base64 characters — roughly 24 MB of image. Same reasoning."""

IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
"""What an OpenAI-compatible endpoint is agreed to accept. Refusing anything else here is the
difference between a clear error and a model being handed a file it will describe as noise."""


class AttachmentIn(BaseModel):
    """A file sent with a message, read in the browser.

    There is no upload endpoint, and that is deliberate rather than unfinished: a *project's*
    files need embeddings and retrieval and are v0.2, while a file attached to one question is
    context for that turn and nothing else.

    Two shapes, and exactly one of them per file: ``text`` for something that decoded as text,
    ``data_url`` for a picture. Sending both, or neither, is rejected rather than resolved by
    precedence — a rule about which one wins is a rule somebody has to remember.
    """

    name: str = Field(min_length=1, max_length=255)
    text: str = Field(default="", max_length=MAX_TEXT_CHARS)
    bytes: int = 0

    data_url: str = Field(default="", max_length=MAX_DATA_URL_CHARS)
    """A picture as ``data:<media type>;base64,…``. The bytes travel rather than a link: the
    endpoint is usually a local server with no route back to the browser that read the file."""

    media_type: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def _one_kind_of_file(self) -> AttachmentIn:
        if self.data_url:
            if self.text:
                raise ValueError(f"{self.name}: an attachment is either text or a picture")
            if self.media_type not in IMAGE_TYPES:
                raise ValueError(
                    f"{self.name}: {self.media_type or 'that'} is not an image Hera "
                    f"can send — {', '.join(sorted(IMAGE_TYPES))}"
                )
            if not self.data_url.startswith(f"data:{self.media_type};base64,"):
                raise ValueError(f"{self.name}: a picture must be a base64 data URL")
        elif not self.text:
            raise ValueError(f"{self.name}: an attachment with nothing in it is not a question")
        return self


class MessageIn(BaseModel):
    text: str = ""
    """What the person typed, ``/commands`` included — the router strips them server-side, so
    the browser must not."""

    attachments: list[AttachmentIn] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def _says_something(self) -> MessageIn:
        """A message has to carry *something*. A file on its own is a fair question."""
        if not self.text.strip() and not self.attachments:
            raise ValueError("a message needs text, a file, or both")
        return self


class RedoIn(BaseModel):
    """Ask again from a message.

    ``text`` left out means "the same question" — *try again* on an answer, or on a question
    whose wording was fine. Sent, it replaces the question, which is what *edit* is. There is
    no third field: everything else about the turn is read from the message being replayed.
    """

    text: str | None = None


class PermissionAnswer(BaseModel):
    """The answer to a permission card."""

    call_ids: list[str] = Field(min_length=1)
    allow: bool
    remember: bool = False
    """Whether to write a rule. **Always allow** has to be visibly different from **Allow
    once** afterwards, or nobody can tell whether the decision stuck."""


class EmotionOut(BaseModel):
    """One stance, as the Emotions screen and the emotion card see it."""

    model_config = ConfigDict(frozen=True)

    kind: str
    description: str
    tone: str

    @classmethod
    def of(cls, emotion: Emotion) -> EmotionOut:
        return cls(kind=emotion.kind, description=emotion.description, tone=emotion.tone)


class EmotionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    emotions: list[EmotionOut]
    customised: bool
    """Whether this is the person's list or the one she ships with. What decides whether
    *Reset* is worth offering."""

    problem: str = ""
    """Why the stored list could not be read, when it could not — the defaults are on screen
    and this says so, rather than a screen that fails to load."""


class EmotionsIn(BaseModel):
    """The whole list, in the order it should be read.

    Whole rather than one at a time: the order is something a person arranges, and three
    endpoints for add, edit and remove would each need to agree about it.
    """

    emotions: list[Emotion] = Field(min_length=1, max_length=64)


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
    """A skill row on the settings screen.

    ``author``, ``license``, ``icon`` and ``version`` are frontmatter keys ``hera_skillsets``
    deliberately does not interpret — it keeps them in ``metadata`` and stays out of the way.
    They are lifted into named fields *here*, where the audience is a screen: a row that has to
    reach into a dictionary for the field it always draws is a row that renders nothing when
    somebody spells the key differently, with no way to tell that from a skill that never had
    a licence.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str
    path: str
    resources: list[str]
    problems: list[str]
    hits: int = 0
    last_used_at: datetime | None = None

    author: str = ""
    license: str = ""
    icon: str = ""
    """One character or emoji from the frontmatter. Empty is the normal case, and the interface
    draws a monogram instead — every row gets a mark, none of them has to."""
    version: str = ""
    homepage: str = ""

    digest: str = ""
    """SHA-256 of the ``SKILL.md``, so a person can compare it with a published list by eye."""

    trust: str = "unknown"
    """``verified``, ``modified`` or ``unknown`` — see :mod:`hera_core.trust`."""

    @classmethod
    def of(
        cls, skill: Skill, usage: SkillUsage | None = None, *, trust: str = "unknown"
    ) -> SkillOut:
        meta = skill.metadata
        return cls(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            path=str(skill.path),
            resources=list(skill.resources),
            problems=list(skill.problems),
            hits=usage.hits if usage is not None else 0,
            last_used_at=usage.last_used_at if usage is not None else None,
            author=meta.get("author", ""),
            license=meta.get("license", ""),
            icon=meta.get("icon", ""),
            version=meta.get("version", ""),
            homepage=meta.get("homepage", ""),
            digest=skill.digest,
            trust=trust,
        )


class SkillIn(BaseModel):
    """A skill written from the interface.

    Enough to be a real ``SKILL.md`` and nothing more: an id, the description retrieval matches
    on, and the body that reaches the model. Everything else — author, licence, an icon — is
    frontmatter a person adds in the file, which is the point of skills being folders.
    """

    id: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=1024)
    body: str = ""

    @field_validator("id")
    @classmethod
    def _usable_id(cls, value: str) -> str:
        """The same rule `hera_skillsets` enforces, applied where a person can be told about
        it: the id ends up in a `/slash` command and in a directory name, and Claude Code
        accepts exactly this much."""
        cleaned = value.strip().lower()
        if not ID_PATTERN.match(cleaned):
            raise ValueError("lowercase letters, digits and hyphens, starting with one of them")
        return cleaned


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

    trust_problem: str = ""
    """Why the trust list could not be read, when it could not. A broken ``trusted.json`` costs
    the verified marks and nothing else — it must not be able to hide the skills themselves."""


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

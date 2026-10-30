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

import base64
import binascii
import json
import re
from datetime import date, datetime
from email.utils import parseaddr
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from hera_skillsets.models import ID_PATTERN
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hera_accounts import SignIn, User
from hera_chats import Chat, Message, Project, Totals, UsageSummary
from hera_core.addresses import is_unspecified
from hera_core.config import (
    InstanceConfig,
    MailConfig,
    MailSecurity,
    ProviderKind,
    Registration,
    validate_provider_name,
)
from hera_core.model_presets import PRESETS, ModelPreset
from hera_memories import MAX_DESCRIPTION, MAX_TEXT
from hera_permissions import Decision
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


class ArtifactOut(BaseModel):
    """One published artifact, as the file bar beside the conversation lists it (ADR 13).

    No id and no title: the filename is the identity and the card's heading is that name
    humanised, by the same transformation ``$lib/tools`` already applies to a tool name. There is
    no ``inline`` here either — that is a property of the *call* that published it, and it rides
    in the persisted event rather than in a listing of a directory.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    bytes: int
    modified_at: datetime


class ArtifactProblem(BaseModel):
    """The browser saying it could not draw an artifact — see :mod:`hera_core.problems`."""

    message: str = Field(min_length=1, max_length=2000)


class ArtifactWrite(BaseModel):
    """A person's edit to a file she published: the whole new text.

    The whole text rather than a patch, because the edit is made in a text box over the file and
    what is saved is what is shown — and because the find-and-replace she uses
    (``artifact_edit``) is built for a writer who cannot see the file.
    """

    text: str


class ArtifactContent(BaseModel):
    """One artifact's current content, for the panel that draws it.

    Text rather than bytes, and JSON rather than the file itself, which is a security decision
    and not a style one: serving an artifact as ``text/html`` from Hera's own origin would give a
    page the model wrote the run of Hera's storage and cookies. The browser builds a sandboxed
    frame from this string instead, so the frame keeps an opaque origin (ADR 13).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    bytes: int
    text: str


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


class QuestionAnswer(BaseModel):
    """A person's reply to the questions one call asked.

    One call, not a list of calls, which is where this differs from :class:`PermissionAnswer`:
    several permissions can be settled with one click because the answer is the same word, and
    two cards cannot — each wants its own sentences. A call may hold several questions (ADR 26),
    so the reply is one answer per question, in the order they were asked.
    """

    call_id: str = Field(min_length=1)
    answers: list[Annotated[str, Field(max_length=8000)]] = Field(min_length=1)
    """What they typed or picked, one per question. Each may be empty: saying nothing is an
    answer, and she is told so rather than being left waiting. Capped because it becomes a tool
    result inside the next prompt, and an unbounded paste there is a context window spent
    without anybody choosing to."""


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

    shared: bool = False
    """Read from the instance's template for everybody (ADR 28). Only an admin changes it, and
    the change is everybody's."""

    @classmethod
    def of(
        cls, region: MindRegion, *, text: str, generation: int, shared: bool = False
    ) -> RegionOut:
        return cls(
            id=region.id,
            title=region.title,
            purpose=region.purpose,
            tier=region.tier.value,
            text=text,
            generation=generation,
            shared=shared,
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

    enabled: bool = True
    """Off means not routed, not offered to `/slash`, not pinnable. The folder stays."""

    @classmethod
    def of(
        cls,
        skill: Skill,
        usage: SkillUsage | None = None,
        *,
        trust: str = "unknown",
        enabled: bool = True,
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
            enabled=enabled,
        )


class SkillPatch(BaseModel):
    enabled: bool


class SkillSource(BaseModel):
    """A skill's ``SKILL.md`` as written — frontmatter and body, the file a person would open."""

    content: str = Field(max_length=200_000)


class SkillIn(BaseModel):
    """A skill written from the interface.

    Enough to be a real ``SKILL.md`` and nothing more: an id, the description retrieval matches
    on, and the body that reaches the model. Everything else — author, licence, an icon — is
    frontmatter a person adds in the file, which is the point of skills being folders.
    """

    id: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=1024)
    body: str = ""
    content: str = Field(default="", max_length=200_000)
    """A whole ``SKILL.md``, written verbatim when given — what the editor sends. Without it the
    file is assembled from ``description`` and ``body``."""

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
    builtin: bool = False
    """Hera's own server. Listed so it can be shown like any other, and not counted as one the
    person added (the composer's "n servers" leaves it out); not the file's to edit."""

    enabled: bool = True
    """False for a block in ``mcp.json`` that is switched off: kept, not started."""

    kind: Literal["builtin", "stdio", "http"] = "stdio"


class ServerEntry(BaseModel):
    """What the add-a-server form edits, and what it is shown when editing.

    ``env`` and ``headers`` values come back as ``None`` where the file holds a literal -- a
    secret somebody pasted never leaves the server -- and a ``None`` sent back means *keep it*.
    A ``${VAR}`` is shown as written, because it is the name of a secret and not one.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["stdio", "http"]
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str | None] = Field(default_factory=dict)
    cwd: str = ""
    url: str = ""
    headers: dict[str, str | None] = Field(default_factory=dict)
    enabled: bool = True


class ServerToolOut(BaseModel):
    """One tool of one server, and whether she has it."""

    model_config = ConfigDict(frozen=True)

    name: str
    """The qualified ``server__tool`` name -- what a rule is written against."""

    local_name: str
    description: str = ""
    allowed: bool
    rule: str | None = None
    """The pattern that turned it off, when something did."""

    exact: bool = False
    """Whether that rule is on this tool alone, as opposed to a wider pattern such as ``fs__*``."""


class ToolAllowedIn(BaseModel):
    allowed: bool


class RuleOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    pattern: str
    decision: str
    reason: str = ""
    profile: str | None = None
    name: str = ""
    """What a person calls it. Display only; the pattern is the identity."""
    source: str = "you"
    """``default`` (ships with Hera), ``you`` (made on the screen), ``card`` (answered "always"
    on a confirmation card) or ``profile`` (from a profile, read-only here)."""
    covers: list[str] = Field(default_factory=list)
    """The tools she has right now that this pattern covers — what makes a glob legible."""


class RuleIn(BaseModel):
    """A new rule."""

    pattern: str = Field(min_length=1, max_length=200)
    decision: Decision
    name: str = Field(default="", max_length=120)
    reason: str = Field(default="", max_length=500)


class RulePatch(BaseModel):
    """What may change about a rule. Not its pattern: that is its identity."""

    name: str | None = Field(default=None, max_length=120)
    decision: Decision | None = None
    reason: str | None = Field(default=None, max_length=500)


class FallbackPatch(BaseModel):
    """What a tool no rule covers gets."""

    fallback: Decision


class MatchesOut(BaseModel):
    """Which tools a pattern would cover, for the live preview in the new-rule form."""

    model_config = ConfigDict(frozen=True)

    pattern: str
    tools: list[str]


class PermissionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    fallback: str
    rules: list[RuleOut]


RESERVED_OPTIONS = frozenset(
    {"model", "messages", "stream", "stream_options", "tools", "tool_choice"}
)
"""Request-body keys a model's ``options`` may not set.

``ChatRequest.extra`` is merged into the body **last**, which is what makes it a general seam
and also what makes this necessary: ``{"messages": []}`` typed into the options field would
replace the conversation with nothing, and the symptom would be a model that has forgotten
everything — indistinguishable from the bug this whole field was added to fix (#63).

Refused rather than dropped. A setting that is silently ignored is worse than one that says no.
"""

MAX_OPTIONS_CHARS = 4_000
"""How large a model's ``options`` may be, serialised. Generous for a handful of flags, small
enough that the field cannot become a second prompt nobody can see."""


def _checked_options(options: dict[str, Any]) -> dict[str, Any]:
    """Options a person typed, or a ``ValueError`` naming what is wrong with them.

    Shared by every schema that accepts them, so the rule cannot differ between registering a
    model and editing one — the same reason ``validate_provider_name`` is a function.
    """
    reserved = sorted(RESERVED_OPTIONS & set(options))
    if reserved:
        raise ValueError(
            f"{', '.join(reserved)} would replace part of the request rather than add to it — "
            "options are for fields Hera does not already send"
        )
    if len(json.dumps(options)) > MAX_OPTIONS_CHARS:
        raise ValueError(f"model options are limited to {MAX_OPTIONS_CHARS} characters")
    return options


class ModelOut(BaseModel):
    """One named model registered on an endpoint."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    options: dict[str, Any] = Field(default_factory=dict)
    context_length: int | None = None
    tool_calling: bool = True
    accepts_images: bool = True
    reasoning_efforts: list[str] = Field(default_factory=list)
    """The ``reasoning_effort`` values this model accepts, asked of the endpoint rather than
    guessed from the id — and **empty means unknown, not "any"**.

    A reasoning control is only drawn when this is non-empty, because the values are not a shared
    vocabulary: OpenRouter's set includes ``minimal``, ``none`` and ``xhigh``, and individual
    models take a subset of even that (``qwen/qwen3.8-27b`` accepts ``xhigh``, ``medium`` and
    ``low`` and rejects ``high``). Offering a value the server refuses fails the whole request,
    not just the setting.
    """
    thinking_toggle: bool = False
    """Whether this model reads ``chat_template_kwargs.enable_thinking`` — the knob most reasoning
    models actually have.

    Asked of the endpoint, from the chat template it published. It is a boolean and not a
    vocabulary because that is the shape every model declaring it wants: MiniCPM5 is
    *Think* / *No Think*, Qwen and GLM the same. ``false`` for an endpoint that has not said.
    """
    thinking_budget: bool = False
    """Whether the model wants a thinking **token budget** rather than a named level.

    A third control shape and the one most easily mistaken for the other two: Anthropic-style
    models take ``max_tokens`` on a thinking block, and offering ``low/medium/high`` to one
    produces a control that does nothing. OpenRouter signals it per model with
    ``reasoning.supports_max_tokens``.
    """
    thinking_source: str = "none"
    """Which of the three sources answered: a server's name, ``"declared"`` for something a person
    entered on this screen, or ``"none"``. Shown beside the control, because a person looking at it
    is entitled to know whether the endpoint said so or they did."""
    thinking_shape: str = "none"
    """Which control this model wants - ``values``, ``budget``, ``toggle`` or ``none``. Decided
    server-side so that the browser and the settings screen cannot disagree about it, and so that
    a model wanting both a list and a switch gets one control rather than two that contradict
    each other."""

    tool_call_shape: str = "unknown"
    """Whether this endpoint's chat template can render a tool declaration - ``template``,
    ``none`` or ``unknown``.

    A fact about the template and nothing more. It is **not** a claim that a call will come back
    as a call: that needs an engine with a parser for the model's dialect, which no endpoint
    publishes, and which for MiniCPM5-2B differs across the four engines it runs on (#145).
    Reported rather than acted on -- nothing is reformatted on the strength of this field,
    because silently changing how a model is asked to call a tool is the guessing ADR 18 exists
    to stop."""


class ProviderOut(BaseModel):
    """One registered endpoint. Never carries the key — see ``api_key_set``."""

    model_config = ConfigDict(frozen=True)

    name: str
    kind: ProviderKind
    base_url: str
    models: list[ModelOut]
    active_model: str
    embedding_model: str
    timeout_s: float
    connect_timeout_s: float
    api_key_set: bool
    logo_media_type: str


class ProvidersOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    providers: list[ProviderOut]
    active: str

    presets: list[ModelPreset] = Field(default_factory=lambda: list(PRESETS))
    """The known request options a model can be given, for the picker beside the options field.

    Served rather than held in the browser, because the server is what validates them — a second
    copy of these values in TypeScript is a second place they can be wrong, and the one that
    would be wrong silently.
    """


class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    """Validated with the same function the stored entry uses, so a bad name is a 422 that
    says what a name may contain rather than a 500 from inside the handler."""

    kind: ProviderKind = "generic"
    base_url: str = Field(min_length=1)

    model_id: str = Field(min_length=1)
    """The first model, registered in the same call that creates the provider — mirrors "the
    first provider added becomes active" for the model living inside it."""
    model_name: str = ""
    model_options: dict[str, Any] = Field(default_factory=dict)
    """Its request options, so a model that needs one can be given it while the endpoint is
    being added rather than in a second visit to the screen."""

    @field_validator("model_options")
    @classmethod
    def _usable_options(cls, options: dict[str, Any]) -> dict[str, Any]:
        return _checked_options(options)

    api_key: str = ""
    embedding_model: str = ""
    timeout_s: float = Field(default=600.0, gt=0)
    connect_timeout_s: float = Field(default=5.0, gt=0)

    @field_validator("name")
    @classmethod
    def _usable_name(cls, name: str) -> str:
        return validate_provider_name(name)


class ProviderPatch(BaseModel):
    """Every field optional. ``None`` means "leave it".

    That is why ``api_key`` is ``str | None`` rather than ``str``: left out it keeps the key
    already on disk, and sent as ``""`` it clears it. A screen that never receives the key
    cannot otherwise preserve one. ``logo_data_url`` follows the same three-state rule: left out
    keeps the stored logo, ``""`` clears it, anything else replaces it.

    Model membership does not travel here — registering, renaming or removing one is
    ``POST``/``DELETE /providers/{name}/models``, and switching which is active is
    ``POST /providers/{name}/activate``.
    """

    kind: ProviderKind | None = None
    base_url: str | None = Field(default=None, min_length=1)
    api_key: str | None = None
    embedding_model: str | None = None
    timeout_s: float | None = Field(default=None, gt=0)
    connect_timeout_s: float | None = Field(default=None, gt=0)

    logo_data_url: str | None = Field(default=None, max_length=MAX_DATA_URL_CHARS)
    logo_media_type: str | None = None

    @model_validator(mode="after")
    def _logo_shape(self) -> ProviderPatch:
        if self.logo_data_url:
            if self.logo_media_type not in IMAGE_TYPES:
                raise ValueError(
                    f"{self.logo_media_type or 'that'} is not an image Hera can store — "
                    f"{', '.join(sorted(IMAGE_TYPES))}"
                )
            prefix = f"data:{self.logo_media_type};base64,"
            if not self.logo_data_url.startswith(prefix):
                raise ValueError("a logo must be a base64 data URL")
            try:
                decoded = base64.b64decode(self.logo_data_url[len(prefix) :], validate=True)
            except binascii.Error as exc:
                raise ValueError("a logo's base64 body is malformed") from exc
            if not decoded:
                raise ValueError("a logo cannot be empty")
        return self


class ModelIn(BaseModel):
    """A model to register on an already-existing endpoint.

    Also how one is **edited**: registering an id that is already there replaces it
    (``ProviderEntry.with_model``), so changing a model's options is this same call rather than
    a route of its own. The consequence worth knowing is that ``options`` is sent whole — an
    empty object clears them.
    """

    id: str = Field(min_length=1, max_length=200)
    name: str = ""
    options: dict[str, Any] = Field(default_factory=dict)
    context_length: int | None = Field(default=None, gt=0)
    """How many tokens this model's window holds, for the composer's usage bar. Never probed —
    see ``ModelEntry.context_length``. ``gt=0`` refuses a bar that couldn't be drawn rather than
    accepting it silently."""

    tool_calling: bool = True
    """Whether this model is offered tools at all (ADR 19). Sent whole, like ``options`` above —
    editing a model without repeating a previously-set ``False`` here puts it back to ``True``."""

    accepts_images: bool = True
    """Whether this model can be shown a picture — see ``ModelEntry.accepts_images``. Sent whole,
    for the same reason as ``tool_calling``."""

    @field_validator("options")
    @classmethod
    def _usable_options(cls, options: dict[str, Any]) -> dict[str, Any]:
        return _checked_options(options)


class ActivateIn(BaseModel):
    """Which model to make active when switching to an endpoint. Empty keeps whichever one was
    already active there."""

    model: str | None = None


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


class PreferencesOut(BaseModel):
    """You and this machine, as the profile menu sees it."""

    model_config = ConfigDict(frozen=True)

    timezone: str
    """IANA name, or empty for UTC alone."""

    now: str
    """The sentence she is actually given this turn.

    Returned rather than left for the screen to reconstruct: the interface would have to format
    a date the same way the prompt does, in a second place, and the first daylight-saving change
    would find out whether the two agreed. Showing the real line also makes the setting
    checkable — you pick a zone and read what she will read.
    """


class PreferencesPatch(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    """``None`` leaves it; ``""`` clears it back to UTC alone."""


class MemoryOut(BaseModel):
    """One memory, as the settings screen lists it (ADR 16).

    Everything the file carries, including what a turn never sees: ``description`` is the line
    a person scans and ``why`` is the provenance, and neither reaches the prompt — so this is
    the only place either of them is ever shown, which is what makes them worth storing.

    ``tokens`` is on the row rather than computed in the browser. What one memory costs and what
    the bar totals have to be the same arithmetic, and two implementations of a rounding rule is
    how a bar ends up disagreeing with the rows above it.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    text: str
    description: str
    why: str
    created: date | None
    scope: str
    chat_id: str
    source: str
    enabled: bool
    tokens: int
    problems: list[str]
    """Anything odd about the file, reported rather than raised -- a memory somebody edited
    badly is listed with the reason beside it, the way a broken skill is."""


class MemoryPatch(BaseModel):
    """What a person may change from the screen. ``None`` means "leave it", as everywhere here.

    No ``key``: the filename is the identity, so renaming a memory would be a different memory
    with the same words in it. And no ``scope``, ``source`` or ``created`` — those record how a
    memory came to exist, and editing the wording of one she wrote does not make it one you
    wrote.
    """

    enabled: bool | None = None
    text: str | None = Field(default=None, max_length=MAX_TEXT)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    why: str | None = Field(default=None, max_length=MAX_DESCRIPTION)


class BudgetOut(BaseModel):
    """What the enabled memories cost, for the bar.

    ``limit`` travels with ``used`` rather than being a constant the browser also knows: it is
    a deployment setting, and a bar drawn against a number the interface guessed would be wrong
    on exactly the installs that changed it.
    """

    model_config = ConfigDict(frozen=True)

    used: int
    limit: int
    count: int
    disabled: int


class HealthOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    version: str
    home: str
    model: str
    skills: int
    servers: list[ServerOut]


class AccountOut(BaseModel):
    """Who is signed in.

    ``avatar_version`` is zero when there is no picture, and otherwise the row's last-change
    time. The interface puts it in the picture's query string, so a replaced picture is a
    different address and a browser holding the old one has no reason to keep showing it.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    email: str
    role: Literal["admin", "user"]
    avatar_version: int

    @classmethod
    def of(cls, user: User) -> AccountOut:
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            role="admin" if user.role == "admin" else "user",
            avatar_version=int(user.updated_at.timestamp()) if user.avatar_type else 0,
        )


_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")
"""The same shape ``hera_accounts`` accepts, and linear for the same reason."""


class AccountPatch(BaseModel):
    """``None`` means *leave it*. An empty name clears it; an email cannot be cleared, because
    it is what a person signs in with."""

    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=254)

    @field_validator("name")
    @classmethod
    def _tidy_name(cls, name: str | None) -> str | None:
        return None if name is None else name.strip()

    @field_validator("email")
    @classmethod
    def _plausible_email(cls, email: str | None) -> str | None:
        if email is None:
            return None
        email = email.strip()
        if not _EMAIL.match(email):
            raise ValueError("that does not look like an email address")
        return email


class SignInIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)


class RegisterIn(BaseModel):
    name: str = Field(default="", max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)


class PasswordIn(BaseModel):
    current: str = Field(max_length=1024)
    new: str = Field(max_length=1024)


class AuthStateOut(BaseModel):
    """What the sign-in screen needs before anybody has signed in, and nothing more.

    Public, so it says only what the login card has to draw: whether the instance is unclaimed,
    whether a stranger may register, and the name to greet them with.
    """

    model_config = ConfigDict(frozen=True)

    user: AccountOut | None
    setup_required: bool
    registration: Registration
    instance_name: str
    reset_by_mail: bool
    """Whether *forgot your password?* can send a link. Says nothing about any address — only
    that mail and a public URL are set up — so the card can say *ask an admin* instead."""


class SessionOut(BaseModel):
    """One signed-in browser, as Settings → Account lists it."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    user_agent: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    current: bool

    @classmethod
    def of(cls, sign_in: SignIn, *, current: UUID) -> SessionOut:
        return cls(
            id=sign_in.id,
            user_agent=sign_in.user_agent,
            created_at=sign_in.created_at,
            last_seen_at=sign_in.last_seen_at,
            expires_at=sign_in.expires_at,
            current=sign_in.id == current,
        )


class SetupOut(BaseModel):
    """Whether this instance still has to be claimed, and what claiming it will need."""

    model_config = ConfigDict(frozen=True)

    required: bool
    code_required: bool
    """``False`` from the machine Hera runs on: somebody at its keyboard needs no code to prove
    they could have read the log."""

    chats: int
    """How many conversations an install from before accounts already has. They become the
    first admin's, and the wizard says so rather than letting it be a surprise."""


class SetupIn(BaseModel):
    name: str = Field(default="", max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)
    code: str = Field(default="", max_length=64)
    launch_token: str = Field(default="", max_length=200)


class InstanceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    public_url: str
    registration: Registration
    suggested_url: str
    """The address this browser reached Hera at, as somebody else would have to type it — what
    the wizard fills the public URL in with, never ``0.0.0.0`` (``hera_core.addresses``)."""

    @classmethod
    def of(cls, instance: InstanceConfig, *, suggested_url: str) -> InstanceOut:
        return cls(
            name=instance.name,
            public_url=instance.public_url,
            registration=instance.registration,
            suggested_url=suggested_url,
        )


class ResetIn(BaseModel):
    email: str = Field(max_length=254)


class LinkIn(BaseModel):
    """The token from an invitation or reset link — the part after ``#``."""

    token: str = Field(min_length=1, max_length=200)


class LinkOut(BaseModel):
    """Who a link is for, so the page it opens can greet them before it is used."""

    model_config = ConfigDict(frozen=True)

    purpose: Literal["invite", "reset"]
    email: str
    name: str
    instance_name: str


class LinkPasswordIn(LinkIn):
    password: str = Field(max_length=1024)


class SentOut(BaseModel):
    """A link made for somebody: whether it went by mail, and the link itself to hand over when
    it did not. ``mail_error`` is the mail server's complaint, empty when there was none."""

    model_config = ConfigDict(frozen=True)

    link: str
    mailed: bool
    mail_error: str = ""


class InvitationIn(BaseModel):
    email: str = Field(max_length=254)
    name: str = Field(default="", max_length=120)
    role: Literal["admin", "user"] = "user"
    """``admin`` only from an admin; a member inviting somebody invites a user."""


class UserOut(BaseModel):
    """One account, as Settings → Admin → Users lists it."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    email: str
    name: str
    role: Literal["admin", "user"]
    disabled: bool
    invited: bool
    """Made, and no password chosen yet: the invitation has not been taken up."""
    created_at: datetime
    last_seen_at: datetime | None
    avatar_version: int

    @classmethod
    def of(cls, user: User, *, invited: bool, last_seen: datetime | None) -> UserOut:
        account = AccountOut.of(user)
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            role=account.role,
            disabled=user.disabled,
            invited=invited,
            created_at=user.created_at,
            last_seen_at=last_seen,
            avatar_version=account.avatar_version,
        )


class InvitationOut(SentOut):
    user: UserOut


class UserPatch(BaseModel):
    role: Literal["admin", "user"] | None = None
    disabled: bool | None = None


class MailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    host: str
    port: int
    security: MailSecurity
    user: str
    sender: str
    sender_name: str
    password_set: bool
    configured: bool
    links_need_public_url: bool
    """A reset asked for by somebody who is not signed in is mailed only with the instance's
    public URL to build the link from (``hera_core.mail``) — true while that is missing."""

    @classmethod
    def of(cls, mail: MailConfig, *, public_url: str) -> MailOut:
        return cls(**mail.redacted(), links_need_public_url=not public_url)


class MailPatch(BaseModel):
    """``None`` leaves a field as it is. ``password`` is the provider key's three states again:
    left out keeps it, ``""`` clears it, anything else replaces it."""

    host: str | None = Field(default=None, max_length=253)
    port: int | None = Field(default=None, ge=1, le=65535)
    security: MailSecurity | None = None
    user: str | None = Field(default=None, max_length=254)
    password: str | None = Field(default=None, max_length=1024)
    sender: str | None = Field(default=None, max_length=330)
    sender_name: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _plausible_sender(self) -> MailPatch:
        """An address, or a whole ``Hera <hera@example.com>`` pasted from somewhere else — split
        into the two fields it means, the name only where none was given alongside it."""
        if self.sender is None or not self.sender.strip():
            return self
        name, address = parseaddr(self.sender.strip())
        if not _EMAIL.match(address):
            raise ValueError("the sender has to be an email address")
        self.sender = address
        if name and self.sender_name is None:
            self.sender_name = name
        return self


class InstancePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    public_url: str | None = Field(default=None, max_length=300)
    registration: Registration | None = None

    @field_validator("public_url")
    @classmethod
    def _somewhere_others_can_reach(cls, url: str | None) -> str | None:
        """Refused here, at the edge, and not in ``InstanceConfig``: a ``config.toml`` already
        holding one must still load, and a link built from it is corrected anyway."""
        host = urlsplit(url.strip()).hostname if url else None
        if host is not None and is_unspecified(host):
            raise ValueError(
                f"{host} means every address of this machine, not one anybody can open; "
                "use its IP address or name"
            )
        return url


class AvatarIn(BaseModel):
    """A picture as a data URL, the way an attachment arrives."""

    data_url: str = Field(min_length=1)


class TokensOut(BaseModel):
    """Prompt and completion tokens, added up."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int
    completion_tokens: int


class UsageDayOut(TokensOut):
    """One local day's bar."""

    date: date


class WindowOut(TokensOut):
    """One rolling window: its tokens, and what is known about them.

    Each extra is ``None`` when nothing in the window measured it: no row reported its cache, no
    turn was timed. The screen leaves such a line out rather than drawing a nought.
    """

    reasoning_tokens: int | None = None
    cache_rate: float | None = None
    """Share of the prompt the endpoint had cached, nought to one, over the turns that said."""

    tokens_per_second: float | None = None
    """Completion tokens over the time spent writing them, as Hera measured it."""

    first_token_ms: float | None = None
    """How long a turn took, on average, before anything came back."""

    @classmethod
    def of_totals(cls, totals: Totals) -> WindowOut:
        return cls(
            prompt_tokens=totals.tokens.prompt_tokens,
            completion_tokens=totals.tokens.completion_tokens,
            reasoning_tokens=totals.reasoning_tokens,
            cache_rate=totals.cache_rate,
            tokens_per_second=totals.tokens_per_second,
            first_token_ms=totals.first_token_ms,
        )


class UsageTotalsOut(BaseModel):
    """The three rolling windows under the chart."""

    model_config = ConfigDict(frozen=True)

    day: WindowOut
    week: WindowOut
    month: WindowOut


class UsageOut(BaseModel):
    """Settings → Usage (#111): a bar per day, oldest first and ending today, and the totals.

    ``timezone`` is the zone the days were cut in, so the screen can say which one it was
    when it is not the browser's own.
    """

    model_config = ConfigDict(frozen=True)

    days: list[UsageDayOut]
    totals: UsageTotalsOut
    timezone: str

    @classmethod
    def of(cls, summary: UsageSummary, timezone: str) -> UsageOut:
        return cls(
            days=[
                UsageDayOut(
                    date=day.date,
                    prompt_tokens=day.tokens.prompt_tokens,
                    completion_tokens=day.tokens.completion_tokens,
                )
                for day in summary.days
            ],
            totals=UsageTotalsOut(
                day=WindowOut.of_totals(summary.day),
                week=WindowOut.of_totals(summary.week),
                month=WindowOut.of_totals(summary.month),
            ),
            timezone=timezone,
        )

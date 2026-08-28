"""What a turn is made of, persisted and streamed.

``hera_providers.Event`` says what a **model** can emit. A turn is a bigger thing than that: a
skill was chosen before the model saw anything, a tool ran after it asked, a person was stopped
and asked whether it may. None of those come out of a model, so none of them belong in that
union — putting them there would mean ``hera_providers`` knowing what a skill, a tool and a
permission are, and it is the one package that must not.

So this union **wraps** that one. Three variants are re-used unchanged, with their ``type``
literals intact, so an event that crossed the provider boundary crosses this one without being
converted. The rest are Hera's own.

**``TurnEnd`` is deliberately not here.** It is the model's full stop for *one round trip*, and
a turn with tools in it contains several — streaming all of them to the browser would mean the
interface has to work out which one was the last. The orchestrator consumes them, adds up their
usage, and closes the turn once with :class:`TurnClosed`. One terminator, no arithmetic in the
client.

Everything downstream keys off ``type`` and nothing parses text. A new kind of thing a turn can
contain is one new variant here, one branch where it is rendered, and nothing else.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from hera_providers import TextDelta, ThinkingDelta, ToolCallReady, Usage

CloseReason = Literal[
    "completed",
    "cancelled",
    "awaiting_permission",
    "awaiting_answer",
    "max_iterations",
    "failed",
]
"""Why a turn stopped.

Wider than the provider's ``FinishReason`` because more can happen to a turn than to a
generation: it can be waiting for a person, or have gone round the tool loop too many times.
``awaiting_permission`` is not a failure — the turn is intact and resumable, and the interface
shows a card rather than an error.

``awaiting_answer`` is the same shape and a different question. A permission card asks *may
I?*; an answer card asks something she wants to know, and the reply is prose rather than a
yes. Two reasons rather than one so the interface can say which is being waited on without
looking at the events before it — and because a turn stopped on a question is not one the
person can settle by clicking *allow*.
"""


class SkillSelected(BaseModel):
    """A skill was given to her, and why (ADR 5).

    Persisted rather than derived, because *why* is not recoverable later: the router's
    decision depended on what the pins were and what the retrieval scores came out as at that
    moment, and both change. ``docs/frontend.md`` shows "she always has this" apart from "she
    went and found this", and this is the field that difference is read from.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["skill_selected"] = "skill_selected"
    skill: str
    reason: Literal["pinned", "slash", "retrieved"]
    score: float | None = None


class ToolResultEvent(BaseModel):
    """What a tool answered — including when it refused, failed or was never reached.

    Mirrors ``hera_tools.ToolResult`` rather than embedding it: this package sits above that
    one and could import it, but the persisted stream is read back by ``apps/core`` and the
    browser, and pinning the shape of a stored event to another package's model makes every
    change there a migration here.

    ``blocks`` keeps the protocol's content list. ADR 4 is explicit that a result can be an
    image or a resource link, and flattening to a string at this boundary is where that
    becomes unrecoverable.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["tool_result"] = "tool_result"
    call_id: str
    tool: str
    ok: bool = True
    failure: str | None = None
    """``denied``, ``unknown_tool``, ``unavailable``, ``timeout`` or ``tool_error``. A plain
    string rather than the enum, so a value added upstream reads through to the interface as
    itself instead of failing validation on a stored event."""

    text: str = ""
    structured: Any = None
    blocks: tuple[dict[str, Any], ...] = ()
    duration_ms: int = 0


class PermissionRequired(BaseModel):
    """A call needs a person to say yes. The turn stops here.

    The one moment the interface blocks. ``reason`` is the deciding rule's own words, which is
    why that field exists in ``hera_permissions`` — "why am I being asked this" should not be
    a question only the configuration file can answer.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["permission_required"] = "permission_required"
    call_id: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class PermissionDecided(BaseModel):
    """A person answered a :class:`PermissionRequired`.

    Recorded so that a reloaded turn shows a settled card instead of live buttons. The
    alternative — the browser inferring it from whether a matching ``tool_result`` turned up
    later — is a rule about event ordering living in the client, which is the shape of the
    thing this whole design exists to avoid.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["permission_decided"] = "permission_decided"
    call_id: str
    allowed: bool
    remembered: bool = False
    """Whether the answer was also written into the policy as a rule. **Always allow** must be
    visibly different from **Allow once** afterwards, or nobody can tell whether it stuck."""


class AnswerRequired(BaseModel):
    """She asked the person something. The turn stops here until they reply.

    The second thing that can suspend a turn, and deliberately the *same* mechanism as the
    first: the turn closes, the events are persisted, and replying starts a new turn that
    resumes the same message. ``docs/tooling.md`` § 4 argued for generalising the permission
    path rather than building a second suspension beside it, and this is that — the only new
    machinery is a reply field instead of two buttons.

    The reply becomes the ``tool_result`` for ``call_id``, which is what lets her carry on
    reading it as an ordinary answer to an ordinary call. Nothing about the model's side of the
    loop knows a person was involved.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["answer_required"] = "answer_required"
    call_id: str
    tool: str
    question: str
    kind: str = ""
    """Her stance while asking, from the same open vocabulary ``hera__emotion`` draws on (ADR
    3). Free text, and an unknown one renders generically — *unsure* and *blocked* are
    different questions and the card is allowed to say which."""


class AnswerGiven(BaseModel):
    """A person replied to an :class:`AnswerRequired`.

    Recorded for the reason :class:`PermissionDecided` is: a reloaded turn has to show a
    settled card rather than a live reply field. Inferring it from whether a ``tool_result``
    turned up later would be a rule about event ordering living in the browser.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["answer_given"] = "answer_given"
    call_id: str
    text: str


class TurnClosed(BaseModel):
    """The turn is over. Exactly one, always last."""

    model_config = ConfigDict(frozen=True)

    type: Literal["turn_closed"] = "turn_closed"
    reason: CloseReason = "completed"
    usage: Usage | None = None
    """Every round trip's usage added together, when the server reported any."""

    iterations: int = 0
    """How many times the model was called. One for a turn with no tools in it."""

    error: str = ""
    """Set when ``reason`` is ``failed``. Written for a person, not for the model."""


ChatEvent = Annotated[
    TextDelta
    | ThinkingDelta
    | ToolCallReady
    | SkillSelected
    | ToolResultEvent
    | PermissionRequired
    | PermissionDecided
    | AnswerRequired
    | AnswerGiven
    | TurnClosed,
    Field(discriminator="type"),
]
"""The persisted stream. Annotate with this; match on the concrete classes."""

CHAT_EVENT_ADAPTER: TypeAdapter[ChatEvent] = TypeAdapter(ChatEvent)
LIST_ADAPTER: TypeAdapter[list[ChatEvent]] = TypeAdapter(list[ChatEvent])
"""Round-trips a whole turn. Persistence goes through the union rather than through each
variant, so surviving a save and a reload stays a property of the union itself."""


def coalesce(events: Sequence[ChatEvent]) -> list[ChatEvent]:
    """Merge consecutive text and thinking fragments into one event each.

    A streamed answer arrives as hundreds of ``text_delta`` events, one per token or so.
    Storing them individually would make a reload replay the typing, cost a row of JSON per
    token, and give the browser nothing it did not already have — the shape is identical, only
    the count differs. Merging happens at the boundary between streaming and storing, so the
    live view and the reloaded one still render the same variants.

    Anything between two fragments stops the merge, so an emotion called mid-sentence stays
    where she put it.
    """
    merged: list[ChatEvent] = []
    for event in events:
        previous = merged[-1] if merged else None
        if isinstance(event, TextDelta) and isinstance(previous, TextDelta):
            merged[-1] = TextDelta(text=previous.text + event.text)
        elif isinstance(event, ThinkingDelta) and isinstance(previous, ThinkingDelta):
            merged[-1] = ThinkingDelta(text=previous.text + event.text)
        else:
            merged.append(event)
    return merged


def visible_text(events: Sequence[ChatEvent]) -> str:
    """Everything she actually said, with the reasoning channel left out.

    Used for the denormalised ``content`` column and for the sidebar's preview. Thinking is
    excluded here for the same reason it is excluded from the history sent back to the model:
    it is not the answer, and treating it as one is how a chat log starts quoting her
    deliberations back at her.
    """
    return "".join(event.text for event in events if isinstance(event, TextDelta))

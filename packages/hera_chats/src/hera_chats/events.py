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

**``ToolCallStarted`` is here and is never persisted**, which is the other half of the same
distinction. It is in the union because it goes to the browser and everything that does is
serialised through here; it is not in :attr:`Turn.recorded` because it is *progress*, and the
stored list is the record of what happened. A call the stream broke off mid-argument never ran,
and history already says a call with no result never ran. The consequence to keep in mind: a
reloaded turn has strictly fewer events than the live one had, and the reducer has to produce
the same rows from both — which it does, because the started row and the ready row are the same
row, keyed on the call id.

Everything downstream keys off ``type`` and nothing parses text. A new kind of thing a turn can
contain is one new variant here, one branch where it is rendered, and nothing else.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from hera_providers import TextDelta, ThinkingDelta, ToolCallReady, ToolCallStarted, Usage

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


class Question(BaseModel):
    """One of the questions in an :class:`AnswerRequired`, and the choices offered for it.

    ``options`` is empty for a question answered in words. When there are some, a person may
    still answer in words — the choices are a shortcut, not a fence.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    options: tuple[str, ...] = ()


class AnswerRequired(BaseModel):
    """She asked the person something. The turn stops here until they reply.

    The second thing that can suspend a turn, and deliberately the *same* mechanism as the
    first: the turn closes, the events are persisted, and replying starts a new turn that
    resumes the same message. It generalises the permission path rather than building a second
    suspension beside it — the only new machinery is a reply field instead of two buttons.

    The reply becomes the ``tool_result`` for ``call_id``, which is what lets her carry on
    reading it as an ordinary answer to an ordinary call. Nothing about the model's side of the
    loop knows a person was involved.

    One call may carry several questions (ADR 26), and they are one card and one reply rather
    than one event each, because they are one call and so have one result.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["answer_required"] = "answer_required"
    call_id: str
    tool: str
    questions: tuple[Question, ...]
    kind: str = ""
    """What sort of question it is — *unsure*, *blocked* or *choice* (ADR 17).

    A closed set on the tool, and a plain ``str`` here, which is the same arrangement
    :attr:`ToolResultEvent.failure` has. This package may not learn what ``hera__ask``'s schema
    says, and a ``Literal`` would also make every turn persisted before the set was closed
    unreadable — an event list is a record of what happened, so it has to keep parsing after the
    tool that produced it has changed. The card draws a kind it does not recognise plainly.

    It used to be a word from the emotion vocabulary, which is why it is worth saying what it is
    not: a question is not a mood, and labelling one *curious* told nobody anything."""

    @model_validator(mode="before")
    @classmethod
    def _one_question(cls, data: object) -> object:
        """Read a turn persisted when a call held one question, as a call holding one.

        The same argument :attr:`kind` stays a ``str`` for: an event list is a record of what
        happened, so it keeps parsing after the tool that produced it has changed. Folded here,
        once, so nothing downstream — the export, the API, the browser — learns there were
        ever two shapes.
        """
        if isinstance(data, dict) and "questions" not in data and "question" in data:
            rest = {key: value for key, value in data.items() if key != "question"}
            return {**rest, "questions": [{"text": data["question"]}]}
        return data


class AnswerGiven(BaseModel):
    """A person replied to an :class:`AnswerRequired`.

    Recorded for the reason :class:`PermissionDecided` is: a reloaded turn has to show a
    settled card rather than a live reply field. Inferring it from whether a ``tool_result``
    turned up later would be a rule about event ordering living in the browser.

    ``answers`` is one reply per question, in the order they were asked.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["answer_given"] = "answer_given"
    call_id: str
    answers: tuple[str, ...]

    @model_validator(mode="before")
    @classmethod
    def _one_answer(cls, data: object) -> object:
        """A reply persisted when there was one question, as one answer — see
        :meth:`AnswerRequired._one_question`."""
        if isinstance(data, dict) and "answers" not in data and "text" in data:
            rest = {key: value for key, value in data.items() if key != "text"}
            return {**rest, "answers": [data["text"]]}
        return data


class TurnTiming(BaseModel):
    """How long the turn's round trips took, measured by Hera from this side of the wire.

    Every endpoint gets this, because it needs nothing from the server: the clock starts when a
    request is sent, *waiting* ends at the first thing that comes back, and *generating* runs from
    there to the round's end. Waiting therefore includes the network and the server reading the
    prompt, which is what a person sitting in front of it waits for.
    """

    model_config = ConfigDict(frozen=True)

    first_token_ms: float | None = None
    """How long the first round took to answer at all: what a person waited for anything."""

    waiting_ms: float = 0.0
    """Every round's wait for its first token, added together."""

    generating_ms: float = 0.0
    """Every round's time from its first token to its end, added together."""

    timed_completion_tokens: int = 0
    """Completion tokens of the rounds that were both timed and counted. Divided by
    ``generating_ms`` it is the speed; dividing all of them would count rounds with no time."""


class TurnClosed(BaseModel):
    """The turn is over. Exactly one, always last."""

    model_config = ConfigDict(frozen=True)

    type: Literal["turn_closed"] = "turn_closed"
    reason: CloseReason = "completed"
    usage: Usage | None = None
    """Every round trip's usage added together, when the server reported any.

    What the turn *cost*. Not how full the context window is: a turn with three tool rounds sends
    the conversation three times, and this counts all three. That is ``context_tokens``.
    """

    context_tokens: int | None = None
    """The last round's prompt and completion: what is in the window once this turn is over, and
    so roughly what the next request starts from. ``None`` when the server reported nothing."""

    timing: TurnTiming | None = None
    """How long it took. ``None`` on a turn that never sent a request."""

    iterations: int = 0
    """How many times the model was called. One for a turn with no tools in it."""

    error: str = ""
    """Set when ``reason`` is ``failed``. Written for a person, not for the model."""


ChatEvent = Annotated[
    TextDelta
    | ThinkingDelta
    | ToolCallStarted
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

    Anything between two fragments stops the merge, so a tool call made mid-sentence stays
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

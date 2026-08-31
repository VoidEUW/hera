"""Stored messages, turned back into the conversation a model is sent.

``hera_prompts`` compiles the *frame* — a system message and a final user message — and says
plainly that it knows no history. This module is the history, and it goes between the two.

The interesting work is one assistant turn becoming **several** wire messages. A turn that
called tools looks like: some text, two calls, two results, more text. An OpenAI-compatible
endpoint wants that as an assistant message carrying the calls, then one ``tool`` message per
result, then a further assistant message. Flattening it into a single assistant message loses
the pairing between a call and its answer, and a model that cannot match ``tool_call_id`` to a
call ignores the result entirely — silently, with the turn continuing as if the tool had never
run.

**A picture is a content part, not text.** ``content_of`` is where that is decided, and it
is the only place in the system that knows a message can be more than a string -- everything
above it hands over attachments and everything below it moves whatever shape it is given.

**Thinking never comes back.** The reasoning channel is not the answer, and replaying it as one
teaches her that deliberating out loud is what an assistant message looks like.

**A very long argument does not come back in full either.** A call's arguments are persisted and
replayed on every later turn, so a tool whose argument *is* a document — a published page, a
scratchpad file — would otherwise sit in the prompt for the rest of the conversation, growing it
by the size of everything she has ever written. Past :data:`MAX_ARGUMENT_CHARS` a string argument
is cut and says so. Nothing here knows which tools those are and it does not need to: the rule is
about size, and a model that needs the rest can read the file back.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict

from hera_chats.events import LIST_ADAPTER, ChatEvent, ToolResultEvent
from hera_chats.models import Message
from hera_providers import (
    ChatMessage,
    ContentPart,
    ImagePart,
    Role,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallReady,
)

__all__ = [
    "MAX_ARGUMENT_CHARS",
    "Attachment",
    "build_history",
    "compose",
    "content_of",
    "events_of",
    "says_something",
    "turn_to_messages",
]


class Attachment(BaseModel):
    """A file sent with a message.

    Two kinds, and which one it is is decided by ``data_url`` rather than by a flag: a file the
    browser could read as text carries its ``text``, a picture carries a ``data:`` URL. Nothing
    here ever holds both, and nothing above has to ask what the file *was* -- it asks what came
    with it.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    text: str = ""
    bytes: int = 0

    data_url: str = ""
    """A picture, base64 in a ``data:`` URL. Empty for a text file.

    The bytes travel rather than a link because the endpoint is usually a local server with no
    route back to the browser that read the file, and a model asked to look at a URL it cannot
    fetch describes the URL instead of the picture.
    """

    media_type: str = ""
    """``image/png`` and friends. Only meaningful alongside ``data_url``."""

    @property
    def is_image(self) -> bool:
        return bool(self.data_url)


FENCE = "```"

MAX_ARGUMENT_CHARS = 4_000
"""How much of one string argument survives into a *later* turn's history.

Not a limit on what she may send: the call went out whole, the event stores it whole, and the
interface shows it whole. This is only about the copy that is replayed underneath every
subsequent question, and without it the conversation grows by the size of every document she has
ever written — a 40 KB page published in turn four is 40 KB of every prompt after it, forever.

Generous enough that an ordinary call is untouched, which is what keeps this invisible: a search
query, a filename, a paragraph of a note all fit. What does not fit is a document, and a document
is exactly the thing she can read back on purpose when she needs it.

The default rather than a setting alone, because a deployment that forgets to configure it should
get the safe behaviour — ``ChatsSettings.max_history_argument_chars`` overrides it, and ``0``
turns it off.
"""


def compose(text: str, attachments: Sequence[Attachment]) -> str:
    """The **words** of a message: what was typed, then each text file in a fenced block.

    The typed question goes first so it is the first thing read rather than the last thing
    after ten kilobytes of source, and each block is named so the model can tell which file it
    is looking at and where it stops.

    A fence inside a file would close the block early, so those are broken with a soft hyphen
    — invisible, and it keeps the structure honest without editing what the file says.

    A picture has no words, so it contributes a *line* rather than a block: the model is shown
    the image itself further down the message, and the name is how a person refers to it ("the
    second screenshot") and how she refers back.
    """
    if not attachments:
        return text
    blocks = [
        f"Attached image: {item.name}" if item.is_image else _fenced(item) for item in attachments
    ]
    return "\n\n".join([text.strip(), *blocks]).strip()


def _fenced(item: Attachment) -> str:
    """One text file as a named, fenced block."""
    return f"Attached file: {item.name}\n{FENCE}\n{item.text.replace(FENCE, '`\u00ad``')}\n{FENCE}"


def content_of(text: str, attachments: Sequence[Attachment]) -> str | list[ContentPart]:
    """What the **model** sees: the words, plus a block per picture.

    A string when nothing needs a block of its own, which is the ordinary case and the shape
    every OpenAI-compatible server has been serving since before parts existed. A list only
    when there is a picture in the message, so an installation that never attaches one never
    sends a request shaped differently from the one it always sent.
    """
    spoken = compose(text, attachments)
    images = [item for item in attachments if item.is_image]
    if not images:
        return spoken
    parts: list[ContentPart] = []
    if spoken.strip():
        parts.append(TextPart(text=spoken))
    parts.extend(ImagePart(url=item.data_url) for item in images)
    return parts


def says_something(content: str | list[ContentPart]) -> bool:
    """Whether this content is worth sending at all.

    A message with neither words nor pictures is an empty user turn, which some servers reject
    and every model finds confusing.
    """
    if isinstance(content, str):
        return bool(content.strip())
    return bool(content)


def attachments_of(message: Message) -> list[Attachment]:
    """The files stored with one message."""
    return [Attachment.model_validate(item) for item in message.attachments]


def events_of(message: Message) -> list[ChatEvent]:
    """The stored event list of one message, validated back into the union."""
    return LIST_ADAPTER.validate_python(message.events)


def build_history(
    messages: Iterable[Message], *, max_argument_chars: int = MAX_ARGUMENT_CHARS
) -> list[ChatMessage]:
    """Every stored message as the wire messages that reproduce the conversation.

    ``max_argument_chars`` cuts a string argument that is really a document — see
    :data:`MAX_ARGUMENT_CHARS`. It applies *here* and not in :func:`turn_to_messages`, which is
    the distinction that matters: the turn in progress replays its own calls in full, because
    what she just wrote is what she is still working on, and only the turns behind it are
    shortened.
    """
    wire: list[ChatMessage] = []
    for message in messages:
        if message.role == "user":
            content = content_of(message.content, attachments_of(message))
            if says_something(content):
                wire.append(ChatMessage(role=Role.USER, content=content))
            continue
        wire.extend(turn_to_messages(events_of(message), max_argument_chars=max_argument_chars))
    return wire


def turn_to_messages(
    events: Sequence[ChatEvent], *, max_argument_chars: int = 0
) -> list[ChatMessage]:
    """One assistant turn's events as the wire messages it is made of.

    Also used mid-turn, to feed a round of tool results back before asking again — so the
    reconstruction the model sees on a reload is the same code path it saw while the turn was
    running, rather than a second implementation that can drift from it.

    ``max_argument_chars`` therefore defaults to **off**: the caller that means the turn in
    progress passes nothing, and :func:`build_history` — the one replaying what is already
    behind her — passes the limit.
    """
    wire: list[ChatMessage] = []
    text: list[str] = []
    calls: list[ToolCall] = []
    results: dict[str, ToolResultEvent] = {}

    def flush() -> None:
        """Close the assistant message in progress and answer its calls."""
        if not text and not calls:
            return
        wire.append(
            ChatMessage(
                role=Role.ASSISTANT,
                content="".join(text),
                tool_calls=list(calls),
            )
        )
        for call in calls:
            result = results.get(call.id)
            wire.append(
                ChatMessage(
                    role=Role.TOOL,
                    tool_call_id=call.id,
                    # A call with no result is one a person was asked about and has not
                    # answered yet, or one the turn was cancelled during. Saying so is far
                    # better than omitting the message: an unanswered tool_call_id is a hole
                    # the model notices and often tries to fill by calling again.
                    content=result.text if result is not None else _unanswered(),
                )
            )
        text.clear()
        calls.clear()

    for event in events:
        if isinstance(event, TextDelta):
            # A round of tool calls closes the assistant message, so text arriving afterwards
            # belongs to the next one.
            if calls:
                flush()
            text.append(event.text)
        elif isinstance(event, ToolCallReady):
            calls.append(
                ToolCall(
                    id=event.id,
                    name=event.name,
                    arguments=_shortened(event.arguments, max_argument_chars),
                )
            )
        elif isinstance(event, ToolResultEvent):
            results[event.call_id] = event

    flush()
    return wire


def _shortened(arguments: Mapping[str, Any], limit: int) -> dict[str, Any]:
    """One call's arguments, with any string long enough to be a document cut short.

    Deliberately a rule about **size** and not about tool names: this package does not know what
    a Hera tool is and must not learn, and the shape it is guarding against — an argument that is
    itself a file — is one any server's tool can have.

    The cut says how much is missing and what to do about it, because the model reads this as its
    own previous message and an argument that silently ends mid-tag is one it will conclude it
    wrote badly. It is not told *which* tool to read it back with: it can see the name of the
    call it is looking at.
    """
    if limit <= 0:
        return dict(arguments)
    cut: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, str) and len(value) > limit:
            missing = len(value) - limit
            cut[key] = (
                f"{value[:limit]}\n… [{missing} more characters, not repeated here — "
                "read it back if you need it]"
            )
        else:
            cut[key] = value
    return cut


def _unanswered() -> str:
    return "this call was never run — the turn stopped before it could be"

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

**Thinking never comes back.** The reasoning channel is not the answer, and replaying it as one
teaches her that deliberating out loud is what an assistant message looks like.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict

from hera_chats.events import LIST_ADAPTER, ChatEvent, ToolResultEvent
from hera_chats.models import Message
from hera_providers import ChatMessage, Role, TextDelta, ToolCall, ToolCallReady

__all__ = ["Attachment", "build_history", "compose", "events_of", "turn_to_messages"]


class Attachment(BaseModel):
    """A file sent with a message."""

    model_config = ConfigDict(frozen=True)

    name: str
    text: str
    bytes: int = 0


FENCE = "```"


def compose(text: str, attachments: Sequence[Attachment]) -> str:
    """What the **model** sees: the message, then each file in a fenced block.

    The one place a file becomes text. The typed question goes first so it is the first thing
    read rather than the last thing after ten kilobytes of source, and each block is named so
    the model can tell which file it is looking at and where it stops.

    A fence inside a file would close the block early, so those are broken with a soft hyphen
    — invisible, and it keeps the structure honest without editing what the file says.
    """
    if not attachments:
        return text
    blocks = [
        f"Attached file: {item.name}\n{FENCE}\n{item.text.replace(FENCE, '`\u00ad``')}\n{FENCE}"
        for item in attachments
    ]
    return "\n\n".join([text.strip(), *blocks]).strip()


def attachments_of(message: Message) -> list[Attachment]:
    """The files stored with one message."""
    return [Attachment.model_validate(item) for item in message.attachments]


def events_of(message: Message) -> list[ChatEvent]:
    """The stored event list of one message, validated back into the union."""
    return LIST_ADAPTER.validate_python(message.events)


def build_history(messages: Iterable[Message]) -> list[ChatMessage]:
    """Every stored message as the wire messages that reproduce the conversation."""
    wire: list[ChatMessage] = []
    for message in messages:
        if message.role == "user":
            content = compose(message.content, attachments_of(message))
            if content.strip():
                wire.append(ChatMessage(role=Role.USER, content=content))
            continue
        wire.extend(turn_to_messages(events_of(message)))
    return wire


def turn_to_messages(events: Sequence[ChatEvent]) -> list[ChatMessage]:
    """One assistant turn's events as the wire messages it is made of.

    Also used mid-turn, to feed a round of tool results back before asking again — so the
    reconstruction the model sees on a reload is the same code path it saw while the turn was
    running, rather than a second implementation that can drift from it.
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
            calls.append(ToolCall(id=event.id, name=event.name, arguments=event.arguments))
        elif isinstance(event, ToolResultEvent):
            results[event.call_id] = event

    flush()
    return wire


def _unanswered() -> str:
    return "this call was never run — the turn stopped before it could be"

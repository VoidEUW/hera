"""The one event union: everything a model can emit, normalised.

This module is the contract the whole system is built around. ``hera_chats`` persists these,
``apps/core`` serialises them to Server-Sent Events, and the browser reduces them into a
message -- so a new kind of thing the model can do is **one new variant here**, not a new
parser somewhere above. The previous version of Hera had a parser on the server and a second
one in the browser that had to stay byte-compatible with it; that is the cost this union
exists to avoid.

Every variant carries a literal ``type`` so the union discriminates on the wire as well as in
Python.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

FinishReason = Literal["stop", "length", "tool_calls", "cancelled"]
"""Why generation stopped, normalised across servers.

``cancelled`` has no equivalent on the wire -- no endpoint reports it, because a cancelled
turn is one the client hung up on. It exists so the layer that aborts a stream can close the
event list with the same shape a finished one has.
"""


class Usage(BaseModel):
    """Token counts, when the server reports them. Many local servers do not."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TextDelta(BaseModel):
    """A fragment of the visible answer."""

    model_config = ConfigDict(frozen=True)

    type: Literal["text_delta"] = "text_delta"
    text: str


class ThinkingDelta(BaseModel):
    """A fragment of the reasoning channel.

    Kept apart from :class:`TextDelta` all the way to the browser, because reasoning is shown
    differently -- collapsed, dimmed, or not at all -- and because it must never be fed back
    into the next turn as if it were the answer.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["thinking_delta"] = "thinking_delta"
    text: str


class ToolCallReady(BaseModel):
    """One complete tool call, ready for a permission check and dispatch.

    Emitted only once the whole call has arrived: the protocol streams ``arguments`` as JSON
    in fragments, and half a JSON object is not something any layer above should have to
    handle. Several of these in one turn is normal -- the target model emits parallel calls,
    which is what makes a turn's worth of emotions cost a single round-trip.

    ``parse_error`` is set instead of raising when the model produced arguments that are not a
    JSON object. One malformed call must not discard the calls that arrived beside it, and the
    turn stays alive: the layer above can feed the error back as a tool result and let the
    model correct itself. ``raw_arguments`` is kept for exactly that message, and for anyone
    debugging why a call did not run.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["tool_call_ready"] = "tool_call_ready"
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    raw_arguments: str = ""
    parse_error: str | None = None


class TurnEnd(BaseModel):
    """The model is done. Always the last event of a stream, exactly once."""

    model_config = ConfigDict(frozen=True)

    type: Literal["turn_end"] = "turn_end"
    reason: FinishReason = "stop"
    usage: Usage | None = None


Event = Annotated[
    TextDelta | ThinkingDelta | ToolCallReady | TurnEnd,
    Field(discriminator="type"),
]
"""The union itself. Annotate with this; match on the concrete classes."""

EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)
"""Validates and dumps a single event.

Persisting and re-reading an event list goes through here rather than through each variant,
so round-tripping stays a property of the union instead of a habit at every call site.
"""

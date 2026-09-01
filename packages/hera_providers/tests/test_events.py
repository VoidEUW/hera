"""The event union itself: discrimination, round-tripping, and what a turn always ends with."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hera_providers import (
    EVENT_ADAPTER,
    Event,
    TextDelta,
    ThinkingDelta,
    ToolCallReady,
    TurnEnd,
    Usage,
)


def test_every_variant_survives_a_json_round_trip() -> None:
    """hera_chats persists these and reads them back; a variant that loses a field on the way
    would show up as a message that renders differently after a reload than it did live."""
    originals: list[Event] = [
        TextDelta(text="hello"),
        ThinkingDelta(text="let me see"),
        ToolCallReady(id="c1", name="hera__search", arguments={"query": "qwen"}),
        TurnEnd(reason="tool_calls", usage=Usage(prompt_tokens=12, completion_tokens=3)),
    ]

    for original in originals:
        payload = EVENT_ADAPTER.dump_python(original, mode="json")
        assert EVENT_ADAPTER.validate_python(payload) == original


def test_the_union_discriminates_on_type() -> None:
    """The discriminator is what lets the browser switch on a variant without parsing text."""
    event = EVENT_ADAPTER.validate_python({"type": "thinking_delta", "text": "hm"})
    assert isinstance(event, ThinkingDelta)


def test_an_unknown_variant_is_rejected_rather_than_guessed() -> None:
    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_python({"type": "audio_delta", "text": "hm"})


def test_events_are_frozen() -> None:
    """An event list is a record of what happened; nothing above may edit it in place."""
    event = TextDelta(text="hello")

    with pytest.raises(ValidationError):
        event.text = "goodbye"  # type: ignore[misc]  # the assignment failing is the test


def test_a_tool_call_without_arguments_is_still_a_complete_call() -> None:
    call = ToolCallReady(id="c1", name="hera__note")
    assert call.arguments == {}
    assert call.parse_error is None

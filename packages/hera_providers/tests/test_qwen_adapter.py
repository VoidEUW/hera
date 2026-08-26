"""The Qwen adapter: reasoning, tool-call assembly, and the shape of the end of a turn."""

from __future__ import annotations

from typing import Any

import pytest

from hera_providers import (
    Event,
    QwenAdapter,
    StreamAdapter,
    TextDelta,
    ThinkingDelta,
    ToolCallReady,
    TurnEnd,
)


def chunk(
    *,
    content: str | None = None,
    reasoning: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    finish: str | None = None,
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    """One stream chunk in the shape an OpenAI-compatible endpoint sends."""
    delta: dict[str, Any] = {}
    if content is not None:
        delta["content"] = content
    if reasoning is not None:
        delta["reasoning_content"] = reasoning
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    payload: dict[str, Any] = {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if usage is not None:
        payload["usage"] = usage
    return payload


def drain(chunks: list[dict[str, Any]]) -> list[Event]:
    adapter = QwenAdapter()
    events = [event for item in chunks for event in adapter.feed(item)]
    events.extend(adapter.finish())
    return events


def texts(events: list[Event]) -> str:
    return "".join(e.text for e in events if isinstance(e, TextDelta))


def thoughts(events: list[Event]) -> str:
    return "".join(e.text for e in events if isinstance(e, ThinkingDelta))


def test_the_adapter_satisfies_the_protocol() -> None:
    adapter: StreamAdapter = QwenAdapter()
    assert list(adapter.finish())


def test_plain_text_streams_through_and_ends_once() -> None:
    events = drain([chunk(content="Hel"), chunk(content="lo"), chunk(finish="stop")])

    assert texts(events) == "Hello"
    assert [e for e in events if isinstance(e, TurnEnd)] == [TurnEnd(reason="stop")]


def test_a_reasoning_field_becomes_thinking() -> None:
    """The server that splits the channel for us is the easy case."""
    events = drain([chunk(reasoning="weighing it"), chunk(content="Yes."), chunk(finish="stop")])

    assert thoughts(events) == "weighing it"
    assert texts(events) == "Yes."


def test_inline_think_tags_are_lifted_out_of_the_content() -> None:
    """The other case: the same model, a server whose template leaves the tags in `content`.

    Both have to arrive above as the same two channels, or every consumer needs to know which
    server it is talking to.
    """
    events = drain([chunk(content="A<think>hm</think>B"), chunk(finish="stop")])

    assert texts(events) == "AB"
    assert thoughts(events) == "hm"


@pytest.mark.parametrize("split", range(1, 27))
def test_a_think_tag_split_across_chunks_reads_the_same(split: int) -> None:
    """The failure this guards against is a `<thi` / `nk>` boundary leaking a tag into the
    visible answer. Every split point of the same content must produce the same two channels."""
    content = "before <think>reasoning</think> after"
    events = drain(
        [chunk(content=content[:split]), chunk(content=content[split:]), chunk(finish="stop")]
    )

    assert texts(events) == "before  after"
    assert thoughts(events) == "reasoning"


def test_content_arriving_one_character_at_a_time_reads_the_same() -> None:
    content = "a<think>b</think>c<think>d</think>e"
    events = drain([*(chunk(content=character) for character in content), chunk(finish="stop")])

    assert texts(events) == "ace"
    assert thoughts(events) == "bd"


def test_an_unterminated_think_block_is_flushed_as_thinking() -> None:
    """A truncated turn must not tip its reasoning into the visible answer."""
    events = drain([chunk(content="A<think>hm and then"), chunk(finish="length")])

    assert texts(events) == "A"
    assert thoughts(events) == "hm and then"
    assert events[-1] == TurnEnd(reason="length")


def test_a_half_written_tag_at_the_end_is_flushed_as_the_text_it_is() -> None:
    events = drain([chunk(content="done <thi"), chunk(finish="stop")])

    assert texts(events) == "done <thi"


def test_parallel_tool_calls_are_assembled_and_emitted_in_index_order() -> None:
    """One turn's worth of emotions costs one round-trip precisely because of this."""
    events = drain(
        [
            chunk(
                tool_calls=[
                    {
                        "index": 0,
                        "id": "c0",
                        "function": {"name": "hera__emotion", "arguments": ""},
                    },
                    {"index": 1, "id": "c1", "function": {"name": "hera__note", "arguments": ""}},
                ]
            ),
            chunk(tool_calls=[{"index": 1, "function": {"arguments": '{"text":'}}]),
            chunk(tool_calls=[{"index": 0, "function": {"arguments": '{"kind":"joke"}'}}]),
            chunk(tool_calls=[{"index": 1, "function": {"arguments": '"ok"}'}}]),
            chunk(finish="tool_calls"),
        ]
    )

    calls = [e for e in events if isinstance(e, ToolCallReady)]
    assert [(c.id, c.name, c.arguments) for c in calls] == [
        ("c0", "hera__emotion", {"kind": "joke"}),
        ("c1", "hera__note", {"text": "ok"}),
    ]
    assert events[-1] == TurnEnd(reason="tool_calls")


def test_a_call_with_no_arguments_is_complete_not_broken() -> None:
    events = drain(
        [
            chunk(tool_calls=[{"index": 0, "id": "c0", "function": {"name": "hera__skill"}}]),
            chunk(finish="tool_calls"),
        ]
    )

    call = next(e for e in events if isinstance(e, ToolCallReady))
    assert call.arguments == {}
    assert call.parse_error is None


def test_a_call_without_an_id_gets_one_derived_from_its_index() -> None:
    """A tool result has to name the call it answers, so an id is not optional above here."""
    events = drain(
        [
            chunk(tool_calls=[{"index": 3, "function": {"name": "x", "arguments": "{}"}}]),
            chunk(finish="tool_calls"),
        ]
    )

    assert next(e for e in events if isinstance(e, ToolCallReady)).id == "call_3"


def test_malformed_arguments_do_not_discard_the_calls_beside_them() -> None:
    """One bad call must not cost the turn. The error travels on the event so the layer above
    can feed it back as a tool result and let the model correct itself."""
    events = drain(
        [
            chunk(
                tool_calls=[
                    {"index": 0, "id": "a", "function": {"name": "bad", "arguments": "{oops"}},
                    {"index": 1, "id": "b", "function": {"name": "good", "arguments": '{"n":1}'}},
                ]
            ),
            chunk(finish="tool_calls"),
        ]
    )

    bad, good = (e for e in events if isinstance(e, ToolCallReady))
    assert bad.arguments == {}
    assert bad.parse_error is not None
    assert bad.raw_arguments == "{oops"
    assert good.arguments == {"n": 1}
    assert good.parse_error is None


def test_arguments_that_are_valid_json_but_not_an_object_are_a_parse_error() -> None:
    events = drain(
        [
            chunk(
                tool_calls=[{"index": 0, "id": "a", "function": {"name": "x", "arguments": "[1]"}}]
            ),
            chunk(finish="tool_calls"),
        ]
    )

    call = next(e for e in events if isinstance(e, ToolCallReady))
    assert call.parse_error is not None
    assert "expected a JSON object" in call.parse_error


def test_a_turn_with_calls_ends_in_tool_calls_even_when_the_server_says_stop() -> None:
    """Some servers report `stop` alongside calls. The reason decides whether the loop runs
    again, so it is normalised here rather than in every consumer."""
    events = drain(
        [
            chunk(
                tool_calls=[{"index": 0, "id": "a", "function": {"name": "x", "arguments": "{}"}}]
            ),
            chunk(finish="stop"),
        ]
    )

    assert events[-1] == TurnEnd(reason="tool_calls")


def test_a_trailing_usage_only_chunk_is_carried_into_the_end() -> None:
    """`stream_options.include_usage` sends the counts in a final chunk with no choices."""
    events = drain(
        [
            chunk(content="hi"),
            chunk(finish="stop"),
            {
                "choices": [],
                "usage": {"prompt_tokens": 9, "completion_tokens": 2, "total_tokens": 11},
            },
        ]
    )

    end = events[-1]
    assert isinstance(end, TurnEnd)
    assert end.usage is not None
    assert end.usage.total_tokens == 11


@pytest.mark.parametrize(
    ("reported", "normalised"),
    [("stop", "stop"), ("length", "length"), ("max_tokens", "length"), ("banana", "stop")],
)
def test_finish_reasons_are_normalised(reported: str, normalised: str) -> None:
    events = drain([chunk(content="x"), chunk(finish=reported)])

    assert events[-1] == TurnEnd(reason=normalised)


def test_a_stream_that_never_reports_a_reason_still_ends() -> None:
    """A dropped connection must not leave the event list without its terminator."""
    assert drain([chunk(content="x")])[-1] == TurnEnd(reason="stop")


def test_finishing_twice_yields_nothing_the_second_time() -> None:
    adapter = QwenAdapter()
    list(adapter.feed(chunk(content="x", finish="stop")))

    assert len(list(adapter.finish())) == 1
    assert list(adapter.finish()) == []


def test_chunks_the_protocol_does_not_promise_are_ignored_rather_than_fatal() -> None:
    """Local servers send keep-alives and odd shapes; none of them should end a turn."""
    events = drain([{}, {"choices": None}, chunk(content="x"), {"choices": [{"delta": {}}]}])

    assert texts(events) == "x"


def test_a_tool_call_fragment_that_is_not_a_mapping_is_skipped() -> None:
    """A malformed fragment must not take the turn down; it is a server bug, not a model one."""
    events = drain(
        [
            chunk(tool_calls=["nonsense"]),  # type: ignore[list-item]  # deliberately wrong shape
            chunk(tool_calls=[{"index": 0, "id": "a", "function": None}]),
            chunk(tool_calls=[{"index": 0, "function": {"name": "x", "arguments": "{}"}}]),
            chunk(finish="tool_calls"),
        ]
    )

    call = next(e for e in events if isinstance(e, ToolCallReady))
    assert (call.id, call.name) == ("a", "x")

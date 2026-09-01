"""FakeProvider: the thing every layer above is tested against.

These double as its documentation. If a pattern is not shown here, it is not a pattern the
rest of the project should be reaching for.
"""

from __future__ import annotations

import pytest

from hera_providers import (
    ChatMessage,
    ChatRequest,
    EmbeddingProvider,
    Event,
    FakeProvider,
    FakeProviderExhausted,
    Provider,
    ProviderUnavailable,
    Role,
    TextDelta,
    ThinkingDelta,
    ToolCallReady,
    ToolCallStarted,
    TurnEnd,
    Usage,
    pseudo_embedding,
    text_turn,
    thinking_turn,
    tool_call,
    tool_turn,
)


def ask(text: str = "why?") -> ChatRequest:
    return ChatRequest(model="fake", messages=[ChatMessage(role=Role.USER, content=text)])


async def collect(provider: FakeProvider, request: ChatRequest) -> list[Event]:
    return [event async for event in provider.stream(request)]


def test_the_fake_satisfies_both_protocols() -> None:
    """Checked by the type checker: the annotations are the assertion. If this stops holding,
    every test above this package that injects the fake stops being a test of the real seam."""
    provider = FakeProvider()
    streaming: Provider = provider
    embedding: EmbeddingProvider = provider

    assert callable(streaming.stream)
    assert callable(embedding.embed)


async def test_a_scripted_turn_streams_its_events() -> None:
    provider = FakeProvider([text_turn("Because ", "the weights are cold.")])

    events = await collect(provider, ask())

    assert events == [
        TextDelta(text="Because "),
        TextDelta(text="the weights are cold."),
        TurnEnd(reason="stop"),
    ]


async def test_turns_are_consumed_in_order() -> None:
    provider = FakeProvider([text_turn("first"), text_turn("second")])

    assert await collect(provider, ask()) == [TextDelta(text="first"), TurnEnd()]
    assert await collect(provider, ask()) == [TextDelta(text="second"), TurnEnd()]
    assert provider.turns_taken == 2


async def test_running_past_the_script_raises_instead_of_repeating() -> None:
    """A loop asking for more turns than were scripted is the runaway this catches. Answering
    it again would hide exactly that."""
    provider = FakeProvider([text_turn("only one")])
    await collect(provider, ask())

    with pytest.raises(FakeProviderExhausted, match="scripted 1 turn"):
        await collect(provider, ask())


async def test_every_request_is_recorded() -> None:
    """Assert against what was sent rather than reaching for a mock."""
    provider = FakeProvider([text_turn("ok")])
    await collect(provider, ask("what is the plan?"))

    assert provider.requests[0].messages[0].content == "what is the plan?"


async def test_a_callable_script_can_answer_the_request_it_is_given() -> None:
    """This is how a tool loop gets driven: ask for a tool, then see the result and answer."""

    def respond(request: ChatRequest) -> list[Event]:
        if any(message.role is Role.TOOL for message in request.messages):
            return text_turn("Chemnitz, then.")
        return tool_turn(tool_call("hera__remember", {"text": "lives in Chemnitz"}))

    provider = FakeProvider(respond)

    first = await collect(provider, ask())
    # `tool_turn` announces each call before it, the way a real stream does.
    assert isinstance(first[0], ToolCallStarted)
    assert isinstance(first[1], ToolCallReady)
    assert first[-1] == TurnEnd(reason="tool_calls")

    with_result = ChatRequest(
        model="fake",
        messages=[
            ChatMessage(role=Role.USER, content="where?"),
            ChatMessage(role=Role.TOOL, content="stored", tool_call_id="call_hera__remember"),
        ],
    )
    assert await collect(provider, with_result) == [TextDelta(text="Chemnitz, then."), TurnEnd()]


async def test_a_scripted_exception_is_raised_instead_of_streamed() -> None:
    """How the failure paths get tested without a broken server."""
    provider = FakeProvider([ProviderUnavailable("nothing is listening")])

    with pytest.raises(ProviderUnavailable):
        await collect(provider, ask())


async def test_a_thinking_turn_keeps_the_two_channels_apart() -> None:
    provider = FakeProvider([thinking_turn("weighing it", "Yes.")])

    events = await collect(provider, ask())

    assert events[0] == ThinkingDelta(text="weighing it")
    assert events[1] == TextDelta(text="Yes.")


async def test_a_tool_turn_can_carry_prose_and_several_parallel_calls() -> None:
    """The normal case for a turn that looks things up: a sentence and several calls, one
    round-trip."""
    provider = FakeProvider(
        [
            tool_turn(
                tool_call("hera__search", {"query": "qwen"}),
                tool_call("hera__search", {"query": "vllm"}, call_id="c2"),
                text="Go on.",
            )
        ]
    )

    events = await collect(provider, ask())

    assert events[0] == TextDelta(text="Go on.")
    assert [e.id for e in events if isinstance(e, ToolCallReady)] == ["call_hera__search", "c2"]
    assert events[-1] == TurnEnd(reason="tool_calls")


def test_a_text_turn_can_report_a_reason_and_usage() -> None:
    events = text_turn("cut off", reason="length", usage=Usage(total_tokens=7))

    assert events[-1] == TurnEnd(reason="length", usage=Usage(total_tokens=7))


# -- embeddings -------------------------------------------------------------------------


async def test_embeddings_are_deterministic_and_normalised() -> None:
    """Derived from a hash, so they carry no meaning -- which is the point. They make the
    plumbing around retrieval testable without asserting on similarity that is not there."""
    provider = FakeProvider()

    first = await provider.embed(["Chemnitz"])
    second = await provider.embed(["Chemnitz"])

    assert first == second
    assert sum(value * value for value in first[0]) == pytest.approx(1.0)


async def test_different_texts_get_different_vectors_in_input_order() -> None:
    vectors = await FakeProvider().embed(["a", "b"])

    assert vectors[0] != vectors[1]
    assert vectors == [pseudo_embedding("a"), pseudo_embedding("b")]


async def test_vectors_a_test_reasons_about_can_be_pinned() -> None:
    provider = FakeProvider(embeddings={"north": [1.0, 0.0], "east": [0.0, 1.0]})

    assert await provider.embed(["north", "east"]) == [[1.0, 0.0], [0.0, 1.0]]


async def test_the_dimension_count_is_configurable() -> None:
    assert len((await FakeProvider(dimensions=3).embed(["x"]))[0]) == 3


# -- the rest of the surface --------------------------------------------------------------


async def test_the_model_list_is_scriptable() -> None:
    assert await FakeProvider(models=["qwen-test"]).models() == ["qwen-test"]


async def test_closing_is_observable() -> None:
    provider = FakeProvider()
    await provider.aclose()

    assert provider.closed

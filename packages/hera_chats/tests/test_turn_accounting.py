"""What a turn cost and how long it took, however it ended (#111).

The cost is every round added up; the context is the last round alone; the time is measured on
this side of the wire. A turn that is stopped or fails keeps the rounds that did finish.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence

import hera_chats.turn as turn_module
import pytest
from chat_support import StubTools, drain

from hera_chats import TurnClosed, TurnContext, TurnOrchestrator
from hera_providers import (
    ChatRequest,
    Event,
    FakeProvider,
    ProviderError,
    TextDelta,
    ToolCallReady,
    TurnEnd,
    Usage,
    text_turn,
)

Make = Callable[..., TurnOrchestrator]


def used(prompt: int, completion: int, *, cached: int | None = None) -> Usage:
    return Usage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        cached_tokens=cached,
    )


def a_tool_round(usage: Usage) -> list[Event]:
    return [
        ToolCallReady(id="c1", name="fs__read_file"),
        TurnEnd(reason="tool_calls", usage=usage),
    ]


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[float]]:
    """A clock that moves a tenth of a second every time it is read."""
    ticks: list[float] = [0.0]

    def tick() -> float:
        ticks[0] += 0.1
        return ticks[0]

    monkeypatch.setattr(turn_module, "_clock", tick)
    yield ticks


async def closed_of(
    make_orchestrator: Make, tools: StubTools, script: Sequence[object]
) -> TurnClosed:
    provider = FakeProvider(list(script))  # type: ignore[arg-type]  # scripted turns
    events = await drain(make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream())
    closed = events[-1]
    assert isinstance(closed, TurnClosed)
    return closed


class TestTheContext:
    async def test_it_is_the_last_round_not_the_sum(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        """Three rounds at about 10k each is 10k of context, not 30k: each round re-sends the
        conversation, so adding them up measures the cost, not the window."""
        closed = await closed_of(
            make_orchestrator,
            tools,
            [
                a_tool_round(used(10_000, 40)),
                a_tool_round(used(10_100, 40)),
                text_turn("done", usage=used(10_200, 300)),
            ],
        )

        assert closed.context_tokens == 10_500
        assert closed.usage is not None
        assert closed.usage.prompt_tokens == 30_300

    async def test_it_is_unknown_when_nothing_was_reported(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        closed = await closed_of(make_orchestrator, tools, [text_turn("ok")])
        assert closed.context_tokens is None


class TestTheExtras:
    async def test_cached_tokens_add_up_where_reported(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        closed = await closed_of(
            make_orchestrator,
            tools,
            [
                a_tool_round(used(1000, 10, cached=0)),
                text_turn("done", usage=used(1100, 20, cached=1000)),
            ],
        )
        assert closed.usage is not None and closed.usage.cached_tokens == 1000

    async def test_an_extra_no_round_reported_stays_unknown(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        closed = await closed_of(
            make_orchestrator,
            tools,
            [a_tool_round(used(1000, 10)), text_turn("done", usage=used(1100, 20))],
        )
        assert closed.usage is not None and closed.usage.cached_tokens is None


class TestTheTime:
    async def test_waiting_and_generating_are_measured(
        self, make_orchestrator: Make, tools: StubTools, clock: list[float]
    ) -> None:
        """Clock reads in `_ask`: sent, first event, end — 0.1 s apart with the fake clock."""
        closed = await closed_of(
            make_orchestrator, tools, [text_turn("one ", "two", usage=used(500, 20))]
        )

        assert closed.timing is not None
        assert closed.timing.first_token_ms == 100.0
        assert closed.timing.waiting_ms == 100.0
        assert closed.timing.generating_ms == 100.0
        assert closed.timing.timed_completion_tokens == 20

    async def test_every_round_adds_its_time_and_the_first_is_the_wait(
        self, make_orchestrator: Make, tools: StubTools, clock: list[float]
    ) -> None:
        closed = await closed_of(
            make_orchestrator,
            tools,
            [a_tool_round(used(1000, 10)), text_turn("done", usage=used(1100, 30))],
        )

        assert closed.timing is not None
        assert closed.timing.first_token_ms == 100.0
        assert closed.timing.waiting_ms == 200.0
        assert closed.timing.generating_ms == 200.0
        assert closed.timing.timed_completion_tokens == 40

    async def test_a_round_without_a_count_adds_no_time_to_the_speed(
        self, make_orchestrator: Make, tools: StubTools, clock: list[float]
    ) -> None:
        """Speed is counted tokens over time; a round with no count has nothing to divide."""
        closed = await closed_of(make_orchestrator, tools, [text_turn("unreported")])

        assert closed.timing is not None
        assert closed.timing.first_token_ms == 100.0
        assert closed.timing.generating_ms == 0.0
        assert closed.timing.timed_completion_tokens == 0


class TestNothingIsLost:
    async def test_a_failed_turn_keeps_the_rounds_that_finished(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        rounds = 0

        def script(request: ChatRequest) -> Sequence[Event]:
            nonlocal rounds
            rounds += 1
            if rounds == 1:
                return a_tool_round(used(2000, 25))
            raise ProviderError("the endpoint went away")

        events = await drain(
            make_orchestrator(FakeProvider(script), tools).begin(TurnContext(text="go")).stream()
        )

        closed = events[-1]
        assert isinstance(closed, TurnClosed)
        assert closed.reason == "failed"
        assert closed.usage is not None and closed.usage.prompt_tokens == 2000
        assert closed.context_tokens == 2025

    async def test_a_stopped_turn_keeps_the_rounds_that_finished(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        """Stop in round two: round one was spent all the same."""
        turn = make_orchestrator(
            FakeProvider(
                [
                    a_tool_round(used(3000, 30)),
                    text_turn("this ", "is ", "cut ", "off", usage=used(3100, 4)),
                ]
            ),
            tools,
        ).begin(TurnContext(text="go"))

        stream = turn.stream()
        async for event in stream:
            if isinstance(event, TextDelta):
                break
        await stream.aclose()

        closed = turn.recorded[-1]
        assert isinstance(closed, TurnClosed)
        assert closed.reason == "cancelled"
        assert closed.usage is not None and closed.usage.prompt_tokens == 3000

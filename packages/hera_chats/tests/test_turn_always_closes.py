"""A turn that dies before it says anything must still leave a record of having died.

The bug this is about: a turn's record is persisted whatever happened -- ``recorded`` is complete
at every moment, and the caller's ``finally`` is what guarantees it -- but the *terminator* was
only written for a ``ProviderError`` and for a cancelled stream. Any other exception, escaping
somewhere between the tool catalogue, the prompt build and the adapter, left ``recorded`` with
nothing in it. The caller still persisted that, so the turn became a message with zero events,
and the transcript drew an empty bubble: a *Try again* button, and no sentence saying the provider
had refused the request. From where a person is standing that is *she had nothing to say*.

The fix is in :meth:`hera_chats.turn.Turn.stream`, which now closes the record on any exception
and re-raises, so the bug is still visible in a traceback while the record survives it.

These drive it through a provider that raises something deliberately **not** a ``ProviderError``
-- the shape nothing covered.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from hera_chats.events import CloseReason

from hera_chats import TurnClosed, TurnContext, TurnOrchestrator
from hera_providers import FakeProvider, ProviderError

pytestmark = pytest.mark.anyio

#: The `make_orchestrator` fixture, as a type. Spelled out rather than imported from
#: `test_turn.py`: the tests directory is not a package, so a relative import cannot reach it, and
#: reaching sideways into another test module for a type alias is a worse coupling than two lines.
Make = Callable[..., TurnOrchestrator]


class NotAProviderError(Exception):
    """Stands in for the failures that are not the provider's fault: a bug in the turn machinery,
    a catalogue that would not load, a frame the adapter did not recognise. Nothing normalised
    these, so nothing closed the record."""


def turn_for(make_orchestrator: Make, failure: Exception) -> TurnOrchestrator:
    return make_orchestrator(FakeProvider([failure]))


async def test_a_turn_that_raises_something_unexpected_still_records_a_terminator(
    make_orchestrator: Make,
) -> None:
    turn = turn_for(
        make_orchestrator, NotAProviderError("the tool catalogue would not load")
    ).begin(TurnContext(text="hi"))

    with pytest.raises(NotAProviderError):
        async for _event in turn.stream():
            pass

    last = turn.recorded[-1]
    assert isinstance(last, TurnClosed), f"the record has no terminator: {turn.recorded!r}"
    assert last.reason == "failed"
    assert "the tool catalogue would not load" in (last.error or "")


async def test_the_reason_names_the_exception_rather_than_pretending(
    make_orchestrator: Make,
) -> None:
    """A blank `error` would draw the same empty bubble with a different sentence, and would throw
    away the one piece of information a person or a bug report actually needs."""
    turn = turn_for(make_orchestrator, NotAProviderError("boom")).begin(TurnContext(text="hi"))

    with pytest.raises(NotAProviderError):
        async for _event in turn.stream():
            pass

    closed = turn.recorded[-1]
    assert isinstance(closed, TurnClosed)
    error = closed.error or ""
    assert "NotAProviderError" in error, "the type is half of what makes it diagnosable"
    assert "boom" in error


async def test_a_provider_error_still_streams_its_close_rather_than_raising(
    make_orchestrator: Make,
) -> None:
    """The existing behaviour, unchanged: a provider failure is an *expected* outcome, so it is
    reported on the stream instead of breaking the connection. This is the distinction the new
    handler is drawn around, and it is worth a test so nobody widens the raise to cover both."""
    turn = turn_for(make_orchestrator, ProviderError("endpoint unreachable")).begin(
        TurnContext(text="hi")
    )

    streamed = [event async for event in turn.stream()]

    assert len(streamed) == 1
    assert isinstance(streamed[0], TurnClosed)
    assert streamed[0].reason == "failed"


async def test_the_record_is_not_closed_twice(make_orchestrator: Make) -> None:
    """`_close` is idempotent, and a caller's late `finally` will want to close whatever is still
    open. A second terminator would leave the record ending in an outcome that did not happen."""
    turn = turn_for(make_orchestrator, ProviderError("unreachable")).begin(TurnContext(text="hi"))

    [event async for event in turn.stream()]
    turn.close("cancelled")  # what a late `finally` would do

    closings = [event for event in turn.recorded if isinstance(event, TurnClosed)]
    assert len(closings) == 1, "the record ends in two different outcomes"
    assert closings[0].reason == "failed", "the first close is the one that describes the turn"


def test_failed_is_a_reason_the_set_allows() -> None:
    """`CloseReason` is a closed set and `failed` has to be in it for the annotation to mean
    anything. Cheap, and it fails loudly if someone ever narrows the set."""
    assert "failed" in CloseReason.__args__  # type: ignore[attr-defined]

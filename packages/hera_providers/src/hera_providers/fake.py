"""A provider that answers from a script.

This is the load-bearing test tool of the whole project. Every layer above -- the tool loop,
the permission prompts, the persisted event stream, the SSE endpoint, the browser reducer --
is exercised against this class, so none of them ever needs a model running. Anything that
genuinely needs a live endpoint is marked ``@pytest.mark.live`` and stays out of CI.

A script is either a list of turns, consumed one per :meth:`FakeProvider.stream` call, or a
callable that decides each turn from the request it is given -- which is how a test drives a
tool loop: turn one asks for a tool, turn two sees the result and answers.

```python
provider = FakeProvider([
    tool_turn(tool_call("hera__emotion", {"kind": "curious", "text": "go on"})),
    text_turn("Because ", "the weights are cold."),
])
```

A turn may also be an ``Exception``, which is raised instead of streamed — and an ``Exception``
*inside* a turn is raised at the point it is reached, so a stream that breaks half way through
is one list rather than a hand-written provider class. Both matter: the first is an endpoint
that is down, the second is the one a turn has to survive, because part of the answer arrived
and is worth persisting.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import Any

from hera_providers.errors import ProviderError
from hera_providers.events import (
    Event,
    FinishReason,
    TextDelta,
    ThinkingDelta,
    ToolCallReady,
    ToolCallStarted,
    TurnEnd,
    Usage,
)
from hera_providers.request import ChatRequest

Turn = Sequence[Event | Exception] | Exception
"""One scripted answer: the events to stream, or the error to raise instead.

An error may also sit *among* the events, where it is raised once everything before it has been
streamed. That is a broken connection rather than an unreachable server, and the two close a
turn differently."""


class FakeProviderExhausted(ProviderError):
    """The script ran out of turns.

    Raised rather than repeating the last turn: a loop that asks for more turns than the test
    scripted is a bug in the loop, and silently answering it again would hide exactly the
    runaway this exception catches.
    """


class FakeProvider:
    """Scripted :class:`~hera_providers.base.Provider` and
    :class:`~hera_providers.base.EmbeddingProvider`."""

    def __init__(
        self,
        script: Sequence[Turn] | Callable[[ChatRequest], Turn] = (),
        *,
        embeddings: Mapping[str, Sequence[float]] | None = None,
        dimensions: int = 8,
        models: Sequence[str] = ("fake-model",),
    ) -> None:
        self._make_turn = script if callable(script) else None
        self._turns: list[Turn] = [] if callable(script) else list(script)
        self._pinned = {text: [float(v) for v in vec] for text, vec in (embeddings or {}).items()}
        self._dimensions = dimensions
        self._models = list(models)

        self.requests: list[ChatRequest] = []
        """Every request received, in order. Assert against this instead of mocking."""

        self.closed = False

    @property
    def turns_taken(self) -> int:
        return len(self.requests)

    async def stream(self, request: ChatRequest) -> AsyncIterator[Event]:
        self.requests.append(request)
        turn = self._next_turn(request)
        if isinstance(turn, Exception):
            raise turn
        for event in turn:
            if isinstance(event, Exception):
                # Reached rather than raised up front, so whatever came before it has already
                # been yielded -- which is the whole difference between "the endpoint is down"
                # and "the connection broke mid-answer", and the second is the one the turn has
                # to keep something from.
                raise event
            yield event

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        """Deterministic unit vectors: the same text always yields the same one.

        Derived from a hash rather than from meaning, so they are useless for judging
        similarity and perfect for checking that the plumbing around retrieval works. Pin the
        vectors that a test actually reasons about through ``embeddings=``.
        """
        return [self._vector(text) for text in texts]

    async def models(self) -> list[str]:
        return list(self._models)

    async def aclose(self) -> None:
        self.closed = True

    def _next_turn(self, request: ChatRequest) -> Turn:
        if self._make_turn is not None:
            return self._make_turn(request)
        index = len(self.requests) - 1
        if index >= len(self._turns):
            raise FakeProviderExhausted(
                f"scripted {len(self._turns)} turn(s), but turn {index + 1} was requested"
            )
        return self._turns[index]

    def _vector(self, text: str) -> list[float]:
        pinned = self._pinned.get(text)
        return list(pinned) if pinned is not None else pseudo_embedding(text, self._dimensions)


def pseudo_embedding(text: str, dimensions: int = 8) -> list[float]:
    """A stable unit vector derived from ``text``."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [digest[index % len(digest)] / 255.0 - 0.5 for index in range(dimensions)]
    norm = math.sqrt(sum(value * value for value in raw)) or 1.0
    return [value / norm for value in raw]


def text_turn(
    *chunks: str, reason: FinishReason = "stop", usage: Usage | None = None
) -> list[Event]:
    """A turn that streams ``chunks`` as visible text and ends.

    Several chunks so a test can prove the consumer reassembles a stream rather than
    happening to work on one whole string.
    """
    return [*(TextDelta(text=chunk) for chunk in chunks), TurnEnd(reason=reason, usage=usage)]


def thinking_turn(thinking: str, *chunks: str) -> list[Event]:
    """A turn that reasons first and then answers."""
    return [ThinkingDelta(text=thinking), *text_turn(*chunks)]


def tool_turn(*calls: ToolCallReady, text: str = "", announce: bool = True) -> list[Event]:
    """A turn that asks for tools. Several calls at once is the normal case, not the corner.

    ``announce`` puts a :class:`ToolCallStarted` in front of each call, which is what a real
    stream does — the name arrives in the first fragment and the whole call much later. On by
    default so that a test written against this fake exercises the same event sequence the
    browser will actually see; a test about what is *persisted* can turn it off, though it does
    not need to, because the turn never records one.
    """
    events: list[Event] = [TextDelta(text=text)] if text else []
    if announce:
        events.extend(ToolCallStarted(id=call.id, name=call.name) for call in calls)
    events.extend(calls)
    events.append(TurnEnd(reason="tool_calls"))
    return events


def tool_call(
    name: str, arguments: dict[str, Any] | None = None, *, call_id: str | None = None
) -> ToolCallReady:
    """A ready tool call, with an id derived from the name so assertions stay readable."""
    return ToolCallReady(
        id=call_id or f"call_{name}",
        name=name,
        arguments=arguments or {},
    )

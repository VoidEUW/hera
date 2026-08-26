"""The protocols everything above this package depends on.

``hera_chats`` takes a :class:`Provider`; the application injects the real one and the tests
inject :class:`~hera_providers.fake.FakeProvider`. Nothing above ever names a concrete class,
which is what lets the whole system be exercised without a model running.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from hera_providers.events import Event
from hera_providers.request import ChatRequest


@runtime_checkable
class Provider(Protocol):
    """Something that can stream a turn.

    ``stream`` is declared as returning an ``AsyncIterator`` rather than as ``async def``, so
    an implementation can be a plain async generator function -- which every one of them is.
    """

    def stream(self, request: ChatRequest) -> AsyncIterator[Event]:
        """Yield events until exactly one :class:`~hera_providers.events.TurnEnd`."""
        ...

    async def aclose(self) -> None:
        """Release whatever the provider holds open."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Something that can turn text into vectors.

    Separate from :class:`Provider` because the two are separately optional: embeddings can be
    switched off without losing chat, and a test double may implement one and not the other.
    """

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        """Return one vector per input, in the order the inputs were given.

        Raises on failure like anything else. Callers that would rather degrade than fail --
        retrieval falling back to keyword overlap, say -- catch
        :class:`~hera_providers.errors.ProviderError` and decide there. That decision belongs
        to the layer that knows whether a missing vector is fatal.
        """
        ...


class StreamAdapter(Protocol):
    """Turns one server's stream chunks into the event union.

    The only place a model family's quirks are allowed to live. Supporting another family is a
    new implementation of this protocol and nothing else -- see ADR 2.
    """

    def feed(self, chunk: Mapping[str, Any]) -> Iterator[Event]:
        """Consume one decoded stream chunk, yielding whatever it completes."""
        ...

    def finish(self) -> Iterator[Event]:
        """Close the stream: flush buffered text, emit collected tool calls, then ``TurnEnd``."""
        ...

"""What Hera's own tools need from the rest of the system, expressed as protocols.

``hera_mcp`` sits below memories, skills and chats and imports no ``hera_*`` package at all, so
the built-in server does not reach for them -- it declares the things it needs and takes them
injected. The port belongs to the consumer, so it says exactly what ``remember`` requires and
nothing about how a memory is stored. The same holds for search: this package knows that she can
look something up, and knows nothing about DuckDuckGo, an API key or an HTTP client.

All of them are async because the implementations touch a database, a git repository or the
network, and a synchronous port would force every one of them through a thread later.

Every port is optional. A deployment that wires none of them still has ``emotion``, and the
other tools answer "not available here" as a tool error the model can read and work around --
which is the whole degradation story of ADR 4 applied to her own capabilities.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Hit:
    """One search result.

    A dataclass rather than a dict because it crosses a seam: the adapter builds it and the
    tool renders it, and the two are in different packages. ``snippet`` is whatever the engine
    returned and is not fetched, cleaned or summarised here -- that would be this package
    deciding what a search result *is*, and it does not know.
    """

    title: str
    url: str
    snippet: str = ""


@runtime_checkable
class Searcher(Protocol):
    """Somewhere to look things up. Implemented by the application, over whichever engine the
    deployment has -- there is no default, because every one of them is a choice about where a
    person's questions go.

    The only port here that leaves the machine, which is why it is worth saying plainly: what
    is passed to :meth:`search` is a query the *model* wrote, and it goes to a third party.
    """

    async def search(self, query: str, *, limit: int) -> Sequence[Hit]:
        """Results for one query, best first, at most ``limit`` of them.

        Returning nothing is a normal answer and not an error -- the tool says so and the model
        tries different words. Raise only when the *engine* failed, so that "no results" and
        "the search is broken" cannot look the same to her.
        """
        ...


@runtime_checkable
class MemoryWriter(Protocol):
    """Somewhere lasting facts go. Implemented by ``hera_memories`` in v0.2."""

    async def remember(self, text: str, *, scope: str) -> str:
        """Store one fact and return a short confirmation for the model.

        ``scope`` is ``"chat"`` for something true of this conversation and ``"global"`` for
        something true of the person. Deduplication is the implementation's business: the
        model will offer the same fact twice and should not be punished for it.
        """
        ...


@runtime_checkable
class NoteWriter(Protocol):
    """Somewhere written documents go -- a notes vault, not a memory."""

    async def write_note(self, text: str, *, title: str = "") -> str:
        """Store one note and return a short confirmation for the model."""
        ...


@dataclass(frozen=True, slots=True)
class ScratchFile:
    """One file in a conversation's scratchpad, as a listing shows it."""

    name: str
    size: int


@runtime_checkable
class Scratchpad(Protocol):
    """Her working files for one conversation (ADR 12).

    Not the notes vault above and not a memory: this is the sheet of paper beside the work,
    where a plan or a half-finished result goes so that the *next* turn can pick it up without
    the whole thing being replayed through the context window.

    Every method takes the conversation it belongs to, because the tools are built once at
    startup and cannot close over one. The id arrives in the call's ``_meta`` -- see
    :data:`hera_mcp.CHAT_ID_META` -- and the implementation is what decides that a name is
    usable, because it is the one holding a filesystem.
    """

    async def write(self, chat_id: str, name: str, text: str, *, append: bool = False) -> str:
        """Write one file and return a short confirmation for the model."""
        ...

    async def read(self, chat_id: str, name: str) -> str | None:
        """The contents of one file, or ``None`` if there is no such file.

        ``None`` rather than an exception for the same reason :meth:`SkillLibrary.load` uses it:
        having looked and found nothing is an ordinary answer, and one she should be told
        plainly enough to try a different name.
        """
        ...

    async def files(self, chat_id: str) -> Sequence[ScratchFile]:
        """Everything in this conversation's scratchpad. Empty is normal, not a failure."""
        ...


@runtime_checkable
class SkillLibrary(Protocol):
    """The ``SKILL.md`` packages on disk. Implemented by ``hera_skillsets``.

    Reachable as a tool even though selection is code (ADR 5): the router injects what applies
    before the turn starts, and this is the door left open for a model that works out mid-task
    that it needs something else. Nothing depends on it being used.
    """

    async def load(self, name: str) -> str | None:
        """The full body of one skill, or ``None`` if there is no such skill."""
        ...

    async def names(self) -> Sequence[str]:
        """Every skill available, for telling the model what it could have asked for."""
        ...

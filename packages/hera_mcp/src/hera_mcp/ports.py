"""What Hera's own tools need from the rest of the system, expressed as protocols.

``hera_mcp`` sits below memories, skills and chats and imports no ``hera_*`` package at all, so
the built-in server does not reach for them -- it declares the things it needs and takes them
injected. The port belongs to the consumer, so it says exactly what ``remember`` requires and
nothing about how a memory is stored. The same holds for search: this package knows that she can
look something up, and knows nothing about DuckDuckGo, an API key or an HTTP client.

All of them are async because the implementations touch a database, a git repository or the
network, and a synchronous port would force every one of them through a thread later.

Every port is optional. A deployment that wires none of them still lists every tool, and the
unwired ones answer "not available here" as a tool error the model can read and work around --
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
class Memories(Protocol):
    """Somewhere lasting facts go. Implemented by ``hera_memories`` (ADR 16).

    **Two methods, and what is missing from them is the design.** There is no way to *list*
    memories, because every enabled one is already in her prompt — a tool that read them back
    would spend the context window on what is already in it, which is the reasoning that left
    ``artifact_list`` out one milestone earlier. And there is no way to *delete* one: what
    ``forget`` does is switch a memory off and keep the file, so nothing a person told her is
    discarded without a person present.
    """

    async def remember(
        self,
        key: str,
        text: str,
        *,
        description: str = "",
        why: str = "",
        scope: str = "global",
        chat_id: str = "",
    ) -> str:
        """Store one fact and return a short confirmation for the model.

        ``key`` is the identity, so writing the same one twice is a correction rather than a
        second copy of a fact that changed. ``scope`` is ``"chat"`` for something true of this
        conversation and ``"global"`` for something true of the person; ``chat_id`` arrives
        from the call's ``_meta`` and never from an argument (ADR 12).

        Raise when it will not fit. The message reaches the model, so it says what is taking the
        space — a refusal it cannot act on is a refusal it will repeat.
        """
        ...

    async def forget(self, key: str) -> str:
        """Stop carrying one memory, keeping the file. Returns a confirmation for the model."""
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
class Artifacts(Protocol):
    """What she publishes for one conversation (ADR 13).

    The other side of the scratchpad above, and the difference is the whole record: a scratchpad
    is hers and nobody reads it, an artifact is the deliverable — named, rendered beside the
    conversation, and downloadable. Two ports rather than one with a flag, because a notes
    directory a person browses for the deliverable is one she has a reason to be tidy in.

    Three methods, matching the three tools. There is deliberately **no listing**: what a person
    sees is a directory the application reads directly, and a tool that enumerated her own output
    back into the context window would spend it on filenames she already knows.

    The implementation decides what a usable name is and enforces :meth:`edit`'s *exactly once*
    rule, because it is the one holding the bytes. Its refusals are read by the model, so they
    say what was wrong and what to do instead.
    """

    async def create(self, chat_id: str, name: str, content: str) -> int:
        """Write one artifact whole, replacing any file of that name. Returns its size in bytes.

        Replacing rather than versioning is the decision ADR 13 took and the cost it accepted:
        there is no undo, and :meth:`edit` is what makes that bearable.
        """
        ...

    async def edit(self, chat_id: str, name: str, find: str, replace: str) -> int:
        """Replace one passage of one artifact. Returns its new size in bytes.

        ``find`` must match **exactly once**. Zero matches and several are both refusals, because
        a replacement that hit the wrong one of three is a silent corruption and the model cannot
        see the file to notice.
        """
        ...

    async def read(self, chat_id: str, name: str) -> str | None:
        """The current content of one artifact, or ``None`` if there is no such file.

        ``None`` rather than an exception for the reason :meth:`Scratchpad.read` uses it: having
        looked and found nothing is an ordinary answer.
        """
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

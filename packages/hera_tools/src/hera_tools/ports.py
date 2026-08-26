"""What Hera's own tools need from the rest of the system, expressed as protocols.

``hera_tools`` sits below memories, skills and chats and may not import them, so the built-in
server does not reach for them -- it declares the three things it needs and takes them
injected. The port belongs to the consumer, so it says exactly what ``remember`` requires and
nothing about how a memory is stored.

All three are async because the implementations will touch a database or a git repository, and
a synchronous port would force every one of them through a thread later.

Every port is optional. A deployment that wires none of them still has ``emotion``, and the
other tools answer "not available here" as a tool error the model can read and work around --
which is the whole degradation story of ADR 4 applied to her own capabilities.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


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

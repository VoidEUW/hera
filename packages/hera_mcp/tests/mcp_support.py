"""Helpers her server's suite imports by name.

Not in `conftest.py`: every conftest resolves to the same module name, so `from conftest import`
picks whichever one pytest imported first — the same reason `hera_chats` has `chat_support.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from hera_mcp import Hit


class FakeMemories:
    """A :class:`~hera_mcp.ports.MemoryWriter` that keeps what it was told."""

    def __init__(self) -> None:
        self.written: list[tuple[str, str]] = []

    async def remember(self, text: str, *, scope: str) -> str:
        self.written.append((text, scope))
        return f"remembered ({scope})"


class FakeNotes:
    """A :class:`~hera_mcp.ports.NoteWriter` that keeps what it was told."""

    def __init__(self) -> None:
        self.written: list[tuple[str, str]] = []

    async def write_note(self, text: str, *, title: str = "") -> str:
        self.written.append((title, text))
        return "written"


class FakeSkills:
    """A :class:`~hera_mcp.ports.SkillLibrary` with one skill in it."""

    def __init__(self) -> None:
        self.bodies = {"writing": "Short sentences. Cut the adverbs."}

    async def load(self, name: str) -> str | None:
        return self.bodies.get(name)

    async def names(self) -> Sequence[str]:
        return sorted(self.bodies)


class FakeSearch:
    """A :class:`~hera_mcp.ports.Searcher` with a scripted answer.

    Scripted rather than stubbed to always return the same thing, because the two answers that
    have to stay distinguishable are *nothing was found* and *the engine broke* — and a fake
    that can only do one of them cannot test that.
    """

    def __init__(self, *hits: Hit, fails: Exception | None = None) -> None:
        self.hits = list(hits)
        self.fails = fails
        self.asked: list[tuple[str, int]] = []

    async def search(self, query: str, *, limit: int) -> Sequence[Hit]:
        self.asked.append((query, limit))
        if self.fails is not None:
            raise self.fails
        return self.hits[:limit]


@asynccontextmanager
async def talking_to(server: MCPServer) -> AsyncIterator[Client]:
    """Open a client for the length of one test, and close it in the same task.

    Not a fixture, and that is the whole point: the SDK's client owns an anyio task group, and
    those are task-affine. pytest-asyncio finalises an async fixture in a different task from
    the one that set it up, so a `yield`ed client unwinds into "cancel scope in a different
    task" — the same trap `hera_tools` answers with a worker task per server.
    """
    async with Client(server=server) as client:
        yield client


def said(result: CallToolResult) -> str:
    """The text the model would read, flattened out of the content blocks."""
    return "".join(getattr(block, "text", "") for block in result.content)

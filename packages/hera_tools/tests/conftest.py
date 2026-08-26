"""Fixtures for the tool layer.

Everything here runs against a real MCP server -- in-process for most tests, a real subprocess
for the stdio ones. There is no mock client: the protocol handshake, the argument validation
and the ``is_error`` convention are exactly the parts worth testing, and a double would be
asserting that our own assumptions agree with themselves.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Sequence

import pytest
from hera_tools.config import StdioServer
from hera_tools.registry import ToolRegistry
from hera_tools.server import ManagedServer
from mcp.server.mcpserver import MCPServer

from hera_permissions import PermissionSet, Policy
from hera_tools import ToolsSettings, build_builtin_server

STDIO_SERVER_SOURCE = """
import os
from mcp.server.mcpserver import MCPServer

server = MCPServer("spike", version="0.1.0")


@server.tool(description="Repeat the text back.")
def echo(text: str) -> str:
    return "echo:" + text


@server.tool(description="Leave without saying goodbye.")
def die() -> str:
    os._exit(9)


server.run(transport="stdio")
"""
"""A whole MCP server as a string, launched with the interpreter running the tests.

Written inline rather than as a file in the test directory so that pytest collection never
tries to import it, and so the thing being launched is visibly a separate process.
"""


class FakeMemories:
    """A :class:`~hera_tools.ports.MemoryWriter` that keeps what it was told."""

    def __init__(self) -> None:
        self.written: list[tuple[str, str]] = []

    async def remember(self, text: str, *, scope: str) -> str:
        self.written.append((text, scope))
        return f"remembered ({scope})"


class FakeNotes:
    def __init__(self) -> None:
        self.written: list[tuple[str, str]] = []

    async def write_note(self, text: str, *, title: str = "") -> str:
        self.written.append((title, text))
        return "note written"


class FakeSkills:
    def __init__(self, bodies: dict[str, str] | None = None) -> None:
        self.bodies = bodies or {"writing": "# Writing\nBe brief."}

    async def load(self, name: str) -> str | None:
        return self.bodies.get(name)

    async def names(self) -> Sequence[str]:
        return sorted(self.bodies)


@pytest.fixture
def settings() -> ToolsSettings:
    """Impatient settings. Nothing in the suite is allowed to take seconds to fail."""
    return ToolsSettings(startup_timeout_s=20.0, call_timeout_s=10.0, retry_after_s=0.0)


@pytest.fixture
def memories() -> FakeMemories:
    return FakeMemories()


@pytest.fixture
def notes() -> FakeNotes:
    return FakeNotes()


@pytest.fixture
def skills() -> FakeSkills:
    return FakeSkills()


@pytest.fixture
def builtin(memories: FakeMemories, notes: FakeNotes, skills: FakeSkills) -> MCPServer:
    return build_builtin_server(memories=memories, notes=notes, skills=skills)


@pytest.fixture
def allow_everything() -> Policy:
    return Policy(base=PermissionSet.of(allow=["*"]))


@pytest.fixture
async def registry(
    builtin: MCPServer, allow_everything: Policy, settings: ToolsSettings
) -> AsyncIterator[ToolRegistry]:
    """Hera's own server, everything allowed, nothing external."""
    registry = ToolRegistry(
        [ManagedServer.in_process("hera", builtin, settings)], policy=allow_everything
    )
    try:
        yield registry
    finally:
        await registry.aclose()


@pytest.fixture
def stdio_config() -> StdioServer:
    return StdioServer(command=sys.executable, args=["-c", STDIO_SERVER_SOURCE])


@pytest.fixture
async def stdio_server(
    stdio_config: StdioServer, settings: ToolsSettings
) -> AsyncIterator[ManagedServer]:
    server = ManagedServer.from_config("spike", stdio_config, settings)
    try:
        yield server
    finally:
        await server.aclose()

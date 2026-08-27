"""Fixtures for the tool layer.

Everything here runs against a real MCP server -- in-process for most tests, a real subprocess
for the stdio ones. There is no mock client: the protocol handshake, the argument validation
and the ``is_error`` convention are exactly the parts worth testing, and a double would be
asserting that our own assumptions agree with themselves.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator

import pytest
from hera_tools.config import StdioServer
from hera_tools.registry import ToolRegistry
from hera_tools.server import ManagedServer
from mcp.server.mcpserver import MCPServer
from tools_support import STDIO_SERVER_SOURCE, TOY_SERVER_NAME, build_toy_server

from hera_permissions import PermissionSet, Policy
from hera_tools import ToolsSettings


@pytest.fixture
def settings() -> ToolsSettings:
    """Impatient settings. Nothing in the suite is allowed to take seconds to fail."""
    return ToolsSettings(startup_timeout_s=20.0, call_timeout_s=10.0, retry_after_s=0.0)


@pytest.fixture
def toy() -> MCPServer:
    return build_toy_server()


@pytest.fixture
def allow_everything() -> Policy:
    return Policy(base=PermissionSet.of(allow=["*"]))


@pytest.fixture
async def registry(
    toy: MCPServer, allow_everything: Policy, settings: ToolsSettings
) -> AsyncIterator[ToolRegistry]:
    """One in-process server, everything allowed, nothing external."""
    registry = ToolRegistry(
        [ManagedServer.in_process(TOY_SERVER_NAME, toy, settings)], policy=allow_everything
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

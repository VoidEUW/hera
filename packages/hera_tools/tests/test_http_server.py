"""The streamable-HTTP transport, against a server that is really listening.

The other half of ADR 4's "both stdio and streamable-http are supported". A remote server is
also the only reason headers exist, so the header path is exercised here rather than asserted
about in isolation -- the failure mode worth catching is a credential that never arrives.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
import uvicorn
from hera_tools.config import HttpServer
from hera_tools.server import ManagedServer
from mcp.server.mcpserver import Context, MCPServer

from hera_tools import ToolsSettings


def _server() -> MCPServer:
    server: MCPServer = MCPServer("remote", version="0.1.0")

    @server.tool(description="Repeat the text back.")
    def echo(text: str) -> str:
        return "echo:" + text

    @server.tool(description="Report the Authorization header we were called with.")
    def whoami(context: Context) -> str:
        request = context.request_context.request
        return request.headers.get("authorization", "anonymous") if request else "no request"

    return server


@pytest.fixture
async def url() -> AsyncIterator[str]:
    """A real HTTP server on an ephemeral port, shut down after the test."""
    config = uvicorn.Config(
        _server().streamable_http_app(), host="127.0.0.1", port=0, log_level="warning"
    )
    running = uvicorn.Server(config)
    task = asyncio.create_task(running.serve())
    try:
        while not running.started:
            await asyncio.sleep(0.01)
        port = running.servers[0].sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        running.should_exit = True
        await task


async def test_it_lists_and_calls(url: str, settings: ToolsSettings) -> None:
    server = ManagedServer.from_config("remote", HttpServer(url=url), settings)
    try:
        assert {tool.name for tool in await server.tools()} == {"remote__echo", "remote__whoami"}

        result = await server.call("echo", {"text": "hi"})

        assert not result.is_error
    finally:
        await server.aclose()


async def test_headers_reach_the_server(url: str, settings: ToolsSettings) -> None:
    """Where an ``Authorization`` value from ``mcp.json`` actually ends up."""
    server = ManagedServer.from_config(
        "remote", HttpServer(url=url, headers={"Authorization": "Bearer hera"}), settings
    )
    try:
        result = await server.call("whoami")
        assert "Bearer hera" in str(result.content)
    finally:
        await server.aclose()


async def test_a_url_nothing_is_listening_on(settings: ToolsSettings) -> None:
    """Degrades like every other unreachable server, with a reason worth showing."""
    server = ManagedServer.from_config("remote", HttpServer(url="http://127.0.0.1:1/mcp"), settings)
    try:
        with pytest.raises(Exception, match=r".+"):
            await server.tools()
        assert server.failure is not None
    finally:
        await server.aclose()

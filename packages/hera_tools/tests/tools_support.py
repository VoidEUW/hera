"""Servers the tool layer's suite runs against, imported by name.

Not in `conftest.py`: every conftest resolves to the same module name, so `from conftest
import` picks whichever one pytest imported first — the same reason `hera_chats` has
`chat_support.py`. Both of these are deliberately somebody else's server rather than Hera's;
what fails here should be the client.
"""

from __future__ import annotations

from mcp.server.mcpserver import Context, MCPServer

STDIO_SERVER_SOURCE = """
import os
from mcp.server.mcpserver import Context, MCPServer

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


TOY_SERVER_NAME = "toy"

TOY_TOOL_COUNT = 3
"""How many tools :func:`build_toy_server` offers. A constant so that a test about a server
being *unreachable* does not fail because a tool was added to the reachable one beside it."""

CALLER_META = "example/callerId"
"""A namespaced ``_meta`` key the toy server reads back.

Deliberately not Hera's. What this package carries is an **opaque** mapping the application
filled in (ADR 12), and a test whose key was ``hera/chatId`` would be asserting that the client
knows what a chat is — which is the one thing it must not.
"""


def build_toy_server() -> MCPServer:
    """A stand-in for whatever in-process server a deployment mounts.

    Deliberately **not** Hera's. Her four tools live in `hera_mcp`, which tests them against a
    real client of its own; what these tests need is *a* server with a couple of tools on it,
    so that a failure here is the client's fault rather than a change to her prompt text. This
    package does not know her server exists, and neither does its suite.
    """
    server: MCPServer = MCPServer(TOY_SERVER_NAME, version="0.1.0")

    @server.tool(description="Answer with a fixed word.")
    def echo(kind: str, text: str = "") -> str:
        return "shown"

    @server.tool(description="Answer with another fixed word.")
    def note(text: str, title: str = "") -> str:
        return "written"

    @server.tool(description="Say what the caller put in the request's _meta.")
    def caller(ctx: Context) -> str:
        meta = getattr(ctx.request_context, "meta", None) or {}
        return str(meta.get(CALLER_META, "nobody"))

    return server

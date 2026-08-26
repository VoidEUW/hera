"""What can go wrong between a tool call and a tool result.

Two families, and the difference decides who is expected to catch them.

**Configuration is fatal at boot.** :class:`InvalidToolConfig` and :class:`InvalidToolName`
mean a human wrote something wrong in ``~/.hera/mcp.json``. They surface once, while starting,
where a person can read them -- not in the middle of a turn.

**Everything else degrades.** A server that will not start, or a call that runs too long,
raises out of :class:`~hera_tools.server.ManagedServer` -- which is usable on its own -- and is
caught by :class:`~hera_tools.registry.ToolRegistry`, which turns it into a failed
:class:`~hera_tools.results.ToolResult`. The model reads the failure as a tool result and can
correct itself; the turn stays alive. ADR 4 puts it as: an unreachable server degrades to a
missing tool.

A tool the catalogue does not have has no exception at all. It is the model inventing a name,
which happens, and the answer is a result listing what does exist -- see
:func:`hera_tools.registry._unknown_tool_text`.
"""

from __future__ import annotations


class ToolsError(Exception):
    """Base class for every error raised by ``hera_tools``."""


class InvalidToolConfig(ToolsError):
    """``mcp.json`` cannot be read, or describes a server that cannot be started.

    Raised while loading, deliberately. A configuration file with a typo in it is not a
    degraded capability -- it is a mistake someone can fix, and it should be said out loud.
    """


class InvalidToolName(ToolsError):
    """A server or tool name that cannot be qualified, or a qualified name that cannot be split.

    See :mod:`hera_tools.naming` for what the rules are and why they are that narrow.
    """


class ServerUnavailable(ToolsError):
    """A server could not be reached, or died while it was being talked to.

    Carries the server name and the underlying failure, because "the tool did not run" is
    never a useful thing to show on its own.
    """

    def __init__(self, server: str, reason: str) -> None:
        super().__init__(f"MCP server {server!r} is unavailable: {reason}")
        self.server = server
        self.reason = reason


class ToolTimeout(ToolsError):
    """A call exceeded the budget the server was given.

    Its own class rather than a flavour of :class:`ServerUnavailable`: the server answered the
    handshake and is presumably still alive, so the next call is worth attempting.
    """

    def __init__(self, tool: str, timeout_s: float) -> None:
        super().__init__(f"tool {tool!r} did not answer within {timeout_s:g}s")
        self.tool = tool
        self.timeout_s = timeout_s

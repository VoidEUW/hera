"""The tool layer: an MCP client.

Tools come from servers declared in ``~/.hera/mcp.json``, in the Claude-Desktop shape, plus any
in-process server the application hands over -- ``hera_mcp`` carries her own capabilities and is
mounted exactly that way, with no special case here. Every tool is namespaced ``server__tool``,
every call is checked by ``hera_permissions`` before it runs, and every call comes back as a
:class:`~hera_tools.results.ToolResult` -- including the ones that were refused or went to a
server that is not running. See ADR 4.

What this package does not do: decide policy (it asks), build prompts, or know what a chat is.
"""

from __future__ import annotations

from hera_tools.catalogue import Catalogue, Tool
from hera_tools.config import (
    HttpServer,
    McpConfig,
    ServerConfig,
    StdioServer,
    expand_variables,
    parse_server,
)
from hera_tools.errors import (
    InvalidToolConfig,
    InvalidToolName,
    ServerUnavailable,
    ToolsError,
    ToolTimeout,
)
from hera_tools.naming import SEPARATOR, qualify, split, validate_server_name
from hera_tools.registry import ServerStatus, ToolRegistry
from hera_tools.results import Failure, ToolInvocation, ToolResult
from hera_tools.server import ManagedServer
from hera_tools.settings import ToolsSettings

__all__ = [
    "SEPARATOR",
    "Catalogue",
    "Failure",
    "HttpServer",
    "InvalidToolConfig",
    "InvalidToolName",
    "ManagedServer",
    "McpConfig",
    "ServerConfig",
    "ServerStatus",
    "ServerUnavailable",
    "StdioServer",
    "Tool",
    "ToolInvocation",
    "ToolRegistry",
    "ToolResult",
    "ToolTimeout",
    "ToolsError",
    "ToolsSettings",
    "expand_variables",
    "parse_server",
    "qualify",
    "split",
    "validate_server_name",
]

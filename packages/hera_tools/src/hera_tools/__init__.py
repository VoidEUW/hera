"""The tool layer: an MCP client, and Hera's own server inside it.

Tools come from servers declared in ``~/.hera/mcp.json``, in the Claude-Desktop shape, plus
one in-process server carrying her own capabilities. Every tool is namespaced ``server__tool``,
every call is checked by ``hera_permissions`` before it runs, and every call comes back as a
:class:`~hera_tools.results.ToolResult` -- including the ones that were refused or went to a
server that is not running. See ADR 4.

What this package does not do: decide policy (it asks), build prompts, or know what a chat is.
"""

from __future__ import annotations

from hera_tools.builtin import BUILTIN_SERVER_NAME, EMOTION_KINDS, build_builtin_server
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
from hera_tools.ports import MemoryWriter, NoteWriter, SkillLibrary
from hera_tools.registry import ServerStatus, ToolRegistry
from hera_tools.results import Failure, ToolInvocation, ToolResult
from hera_tools.server import ManagedServer
from hera_tools.settings import ToolsSettings, hera_home

__all__ = [
    "BUILTIN_SERVER_NAME",
    "EMOTION_KINDS",
    "SEPARATOR",
    "Catalogue",
    "Failure",
    "HttpServer",
    "InvalidToolConfig",
    "InvalidToolName",
    "ManagedServer",
    "McpConfig",
    "MemoryWriter",
    "NoteWriter",
    "ServerConfig",
    "ServerStatus",
    "ServerUnavailable",
    "SkillLibrary",
    "StdioServer",
    "Tool",
    "ToolInvocation",
    "ToolRegistry",
    "ToolResult",
    "ToolTimeout",
    "ToolsError",
    "ToolsSettings",
    "build_builtin_server",
    "expand_variables",
    "hera_home",
    "parse_server",
    "qualify",
    "split",
    "validate_server_name",
]

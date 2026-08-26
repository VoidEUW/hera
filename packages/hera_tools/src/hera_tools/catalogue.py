"""What tools exist, under the names the model is shown.

The catalogue is the only place that knows a tool's qualified name maps to a particular
server, and it is deliberately a value: it is built by asking every server what it has, then
handed around as a snapshot. A turn that has started should not have the tools change
underneath it.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from mcp.types import Tool as McpTool
from pydantic import BaseModel, ConfigDict, Field

from hera_tools.naming import qualify

EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


class Tool(BaseModel):
    """One tool, as the rest of the system sees it.

    Not a re-export of the MCP ``Tool``: this one carries the qualified name and the server it
    came from, and drops the parts of the protocol type nothing here reads. Keeping our own
    shape is also what stops the SDK's types from leaking upwards into ``hera_chats``.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    """The namespaced ``server__tool`` name. This is what the model calls."""

    server: str
    local_name: str
    """The name the server itself uses, which is what gets sent back to it."""

    title: str = ""
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=lambda: dict(EMPTY_SCHEMA))

    @classmethod
    def from_mcp(cls, server: str, tool: McpTool) -> Tool:
        return cls(
            name=qualify(server, tool.name),
            server=server,
            local_name=tool.name,
            title=tool.title or "",
            description=tool.description or "",
            input_schema=tool.input_schema or dict(EMPTY_SCHEMA),
        )

    def as_function_spec(self) -> dict[str, Any]:
        """The shape an OpenAI-compatible endpoint wants.

        A plain dict rather than ``hera_providers.ToolSpec``, because this package does not
        import that one -- the two sit side by side and the turn maps between them. The keys
        are the ones that type expects, so the mapping is ``ToolSpec(**spec)``.
        """
        return {
            "name": self.name,
            "description": self.description or self.title,
            "parameters": self.input_schema or dict(EMPTY_SCHEMA),
        }


class Catalogue(BaseModel):
    """Every tool currently on offer, from every reachable server."""

    model_config = ConfigDict(frozen=True)

    tools: tuple[Tool, ...] = ()

    @classmethod
    def of(cls, tools: Iterable[Tool]) -> Catalogue:
        """Build one, sorted by name so two catalogues over the same servers compare equal."""
        return cls(tools=tuple(sorted(tools, key=lambda tool: tool.name)))

    def get(self, name: str) -> Tool | None:
        """The tool with this qualified name, or ``None`` -- including for a name the model
        invented, which is the common case and not an error here."""
        return next((tool for tool in self.tools if tool.name == name), None)

    def names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self.tools)

    def for_server(self, server: str) -> Catalogue:
        return Catalogue(tools=tuple(tool for tool in self.tools if tool.server == server))

    def as_function_specs(self) -> list[dict[str, Any]]:
        """The whole catalogue, ready to go into a request's ``tools``."""
        return [tool.as_function_spec() for tool in self.tools]

    def __len__(self) -> int:
        return len(self.tools)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and self.get(name) is not None

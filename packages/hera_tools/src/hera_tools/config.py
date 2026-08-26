"""``~/.hera/mcp.json``: which servers exist and how to reach them.

The file is the Claude-Desktop ``mcpServers`` shape, so a block can be copied between the two
configurations unchanged -- that compatibility is the point of ADR 4 and the reason unknown
keys are ignored rather than rejected. A server is stdio if it declares ``command`` and
streamable-http if it declares ``url``; there is no ``type`` field to disagree with.

Two additions of our own, both optional and both harmless to Claude Desktop: ``enabled``, so a
server can be switched off without deleting its block, and the two timeouts, because "time out
per server" is otherwise a single global number that has to suit both a local script and a
remote API.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hera_tools.errors import InvalidToolConfig
from hera_tools.naming import validate_server_name

_VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
"""``${VAR}`` and ``${VAR:-fallback}``, the two shell forms worth supporting."""


def expand_variables(text: str, environ: Mapping[str, str] | None = None) -> str:
    """Substitute ``${VAR}`` references from the environment.

    An API key does not belong in a configuration file that gets copied between machines, so
    the usual way to write one is ``"env": {"TOKEN": "${GITHUB_TOKEN}"}``. A variable that is
    not set raises instead of expanding to an empty string: launching a server with a blank
    credential produces a confusing authentication failure minutes later, where the missing
    variable is the thing that actually went wrong.
    """
    source = os.environ if environ is None else environ

    def replace(match: re.Match[str]) -> str:
        name, fallback = match.group(1), match.group(2)
        value = source.get(name)
        if value is not None:
            return value
        if fallback is not None:
            return fallback
        raise InvalidToolConfig(
            f"${{{name}}} is referenced in mcp.json but not set in the environment"
        )

    return _VARIABLE.sub(replace, text)


class _ServerBase(BaseModel):
    """What every server declaration shares.

    ``extra="ignore"`` is the Claude-Desktop compatibility clause: a block carrying keys this
    client does not implement -- ``alwaysAllow``, an editor's own annotations -- has to keep
    working, because the whole promise is that the block can be copied.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    enabled: bool = True
    """Set to ``false`` to keep the block but not start the server."""

    timeout_s: float | None = None
    """How long one tool call may take. ``None`` uses the registry's default."""

    startup_timeout_s: float | None = None
    """How long the connection and handshake may take. ``None`` uses the registry's default.

    Separate from ``timeout_s`` because the two fail for different reasons: a cold ``npx``
    downloading a package is slow once, a tool that hangs is slow every time.
    """


class StdioServer(_ServerBase):
    """A server started as a subprocess and spoken to over its stdin and stdout."""

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    """Merged over the inherited environment, not a replacement for it."""

    cwd: str | None = None


class HttpServer(_ServerBase):
    """A server reached over streamable HTTP."""

    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    """Sent with every request. This is where an ``Authorization`` value goes."""


ServerConfig = StdioServer | HttpServer
"""One declaration, in whichever of the two shapes it was written."""


def parse_server(name: str, payload: Mapping[str, Any]) -> ServerConfig:
    """Turn one ``mcpServers`` entry into a configuration object.

    Which class it becomes follows from the keys present, the way Claude Desktop reads it.
    Variable references are expanded here, so everything downstream deals in resolved values.
    """
    validate_server_name(name)

    resolved = _expand(payload)
    has_command = bool(resolved.get("command"))
    has_url = bool(resolved.get("url"))

    if has_command and has_url:
        raise InvalidToolConfig(
            f"MCP server {name!r} declares both 'command' and 'url'; it is one or the other"
        )
    if has_command:
        return StdioServer.model_validate(resolved)
    if has_url:
        return HttpServer.model_validate(resolved)
    raise InvalidToolConfig(
        f"MCP server {name!r} declares neither 'command' (stdio) nor 'url' (streamable http)"
    )


def _expand(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Expand ``${VAR}`` in every string the declaration contains, at any depth."""

    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return expand_variables(value)
        if isinstance(value, Mapping):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        return value

    return {key: walk(value) for key, value in payload.items()}


class McpConfig(BaseModel):
    """Every server declared in one file."""

    model_config = ConfigDict(frozen=True)

    servers: dict[str, ServerConfig] = Field(default_factory=dict)

    @classmethod
    def parse(cls, payload: Mapping[str, Any]) -> McpConfig:
        """Read the ``mcpServers`` object of an already-decoded document."""
        declared = payload.get("mcpServers", {})
        if not isinstance(declared, Mapping):
            raise InvalidToolConfig("'mcpServers' must be an object mapping name to server")
        return cls(
            servers={
                name: parse_server(name, _entry(name, entry)) for name, entry in declared.items()
            }
        )

    @classmethod
    def load(cls, path: Path) -> McpConfig:
        """Read a file, or return an empty configuration if there is none.

        A missing file is not an error. A fresh ``~/.hera`` has no ``mcp.json`` in it, and Hera
        with no external tools is a working installation -- her own server is in-process and
        does not come from here.
        """
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return cls()
        except OSError as exc:
            raise InvalidToolConfig(f"cannot read {path}: {exc}") from exc

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidToolConfig(f"{path} is not valid JSON: {exc}") from exc

        if not isinstance(payload, Mapping):
            raise InvalidToolConfig(f"{path} must contain a JSON object")
        return cls.parse(payload)

    def enabled(self) -> dict[str, ServerConfig]:
        """Only the servers that should actually be started."""
        return {name: server for name, server in self.servers.items() if server.enabled}


def _entry(name: str, entry: Any) -> Mapping[str, Any]:
    if not isinstance(entry, Mapping):
        raise InvalidToolConfig(
            f"MCP server {name!r} must be an object, got {type(entry).__name__}"
        )
    return entry

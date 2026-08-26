"""Where the configuration lives and how patient the client is.

Read from ``HERA_TOOLS_*`` environment variables, like every other package's settings.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_HOME = Path("~/.hera")
CONFIG_FILENAME = "mcp.json"


def hera_home() -> Path:
    """The data directory, ``HERA_HOME`` or ``~/.hera``.

    Defined here because ``hera_tools`` is the first package that needs to find a file inside
    it. It is four lines and has no dependencies; when a second package needs the same answer,
    lift it rather than copy it.
    """
    return Path(os.environ.get("HERA_HOME") or DEFAULT_HOME).expanduser()


class ToolsSettings(BaseSettings):
    """Boot settings for the MCP client."""

    model_config = SettingsConfigDict(env_prefix="HERA_TOOLS_", extra="ignore")

    config_path: Path | None = None
    """Where ``mcp.json`` is. ``None`` means ``$HERA_HOME/mcp.json``."""

    startup_timeout_s: float = 30.0
    """How long a server gets to start and complete the handshake.

    Generous, because the common stdio server is an ``npx`` command that may download a
    package on its first run. A server that exceeds it is marked unavailable and its tools
    simply do not appear -- nothing waits on it twice.
    """

    call_timeout_s: float = 60.0
    """How long one tool call may take before it comes back as a failed result."""

    retry_after_s: float = 30.0
    """How long a server that failed to start is left alone before it is tried again.

    Without this, one failure at boot means the server stays missing until Hera restarts; with
    it, plugging a laptop back in is enough. Retrying on every single call instead would pay
    the full startup timeout for each one.
    """

    def resolved_config_path(self) -> Path:
        return self.config_path if self.config_path is not None else hera_home() / CONFIG_FILENAME

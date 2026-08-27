"""Where Hera keeps her data, and the well-known paths inside it.

The one thing every package agrees on. It reads an environment variable and joins a few
path segments; it opens nothing, creates nothing and caches nothing.

Not caching is deliberate. A cached home would be captured at import time, which is before
a test fixture has had a chance to point it somewhere temporary — and the failure mode of
getting that wrong is writing into a real ``~/.hera`` during a test run.
"""

from __future__ import annotations

import os
from pathlib import Path

HOME_ENV = "HERA_HOME"
"""Environment variable that overrides the data directory."""

DEFAULT_HOME = Path("~/.hera")
"""Where everything lives when ``HERA_HOME`` says nothing."""

MIND_DIRNAME = "mind"
SKILLS_DIRNAME = "skills"
DATABASE_FILENAME = "hera.sqlite3"
MCP_FILENAME = "mcp.json"
CONFIG_FILENAME = "config.toml"

__all__ = [
    "CONFIG_FILENAME",
    "DATABASE_FILENAME",
    "DEFAULT_HOME",
    "HOME_ENV",
    "MCP_FILENAME",
    "MIND_DIRNAME",
    "SKILLS_DIRNAME",
    "config_path",
    "database_path",
    "home",
    "mcp_path",
    "mind_dir",
    "skills_dir",
]


def home() -> Path:
    """The data directory: ``$HERA_HOME`` if set and non-empty, otherwise ``~/.hera``.

    An empty ``HERA_HOME`` counts as unset. Exporting a variable to the empty string is a
    common shell accident, and resolving it would put the data directory at the process's
    working directory — somewhere different on every launch.
    """
    return Path(os.environ.get(HOME_ENV) or DEFAULT_HOME).expanduser()


def mind_dir() -> Path:
    """The git repository holding one file per mind region."""
    return home() / MIND_DIRNAME


def skills_dir() -> Path:
    """The directory holding one ``SKILL.md`` package per subdirectory."""
    return home() / SKILLS_DIRNAME


def database_path() -> Path:
    """The SQLite file holding everything relational."""
    return home() / DATABASE_FILENAME


def mcp_path() -> Path:
    """The MCP server configuration, in the Claude-Desktop ``mcpServers`` shape."""
    return home() / MCP_FILENAME


def config_path() -> Path:
    """Boot settings."""
    return home() / CONFIG_FILENAME

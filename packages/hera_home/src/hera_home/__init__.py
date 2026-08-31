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
MEMORIES_DIRNAME = "memories"
CHATS_DIRNAME = "chats"
SCRATCH_DIRNAME = "scratch"
ARTIFACTS_DIRNAME = "artifacts"
DATABASE_FILENAME = "hera.sqlite3"
MCP_FILENAME = "mcp.json"
CONFIG_FILENAME = "config.toml"

__all__ = [
    "ARTIFACTS_DIRNAME",
    "CHATS_DIRNAME",
    "CONFIG_FILENAME",
    "DATABASE_FILENAME",
    "DEFAULT_HOME",
    "HOME_ENV",
    "MCP_FILENAME",
    "MEMORIES_DIRNAME",
    "MIND_DIRNAME",
    "SCRATCH_DIRNAME",
    "SKILLS_DIRNAME",
    "artifacts_dir",
    "chat_dir",
    "chats_dir",
    "config_path",
    "database_path",
    "home",
    "mcp_path",
    "memories_dir",
    "mind_dir",
    "scratch_dir",
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


def memories_dir() -> Path:
    """One markdown file per memory — what she knows about you, across every conversation.

    A directory of files rather than a table, and the reason is the one thing here a person may
    want somewhere else: a chat is Hera-shaped and a memory is not. Files can be read, edited,
    diffed, backed up and handed to another tool without Hera being involved (ADR 16).
    """
    return home() / MEMORIES_DIRNAME


def chats_dir() -> Path:
    """Where everything a single conversation owns on disk lives, one directory per chat."""
    return home() / CHATS_DIRNAME


def chat_dir(chat_id: str) -> Path:
    """One conversation's directory. The id is the name, and nothing else is.

    ``chat_id`` reaches this from a tool call, which means it reaches it from *somewhere*, and
    the answer to how much this function trusts it is **not at all**: anything that is not a
    single plain path segment raises. A ``..`` here would put a scratchpad in the mind
    repository, and a leading ``/`` would put it outside ``~/.hera`` altogether.
    """
    if not chat_id or chat_id in {".", ".."} or "/" in chat_id or "\\" in chat_id:
        raise ValueError(f"not a usable chat id: {chat_id!r}")
    return chats_dir() / chat_id


def scratch_dir(chat_id: str) -> Path:
    """One conversation's scratchpad — hers to write, and gone when the chat is (ADR 12)."""
    return chat_dir(chat_id) / SCRATCH_DIRNAME


def artifacts_dir(chat_id: str) -> Path:
    """One conversation's artifacts — what she publishes, and a person opens (ADR 13).

    A directory of its own beside the scratchpad rather than a flag in it, and the reason belongs
    to the *scratchpad*: it was built to be somewhere she can think out loud unread, and a
    directory a person browses for the deliverable is one she has a reason to be tidy in.
    """
    return chat_dir(chat_id) / ARTIFACTS_DIRNAME


def database_path() -> Path:
    """The SQLite file holding everything relational."""
    return home() / DATABASE_FILENAME


def mcp_path() -> Path:
    """The MCP server configuration, in the Claude-Desktop ``mcpServers`` shape."""
    return home() / MCP_FILENAME


def config_path() -> Path:
    """Boot settings."""
    return home() / CONFIG_FILENAME

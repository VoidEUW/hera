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
LOGOS_DIRNAME = "logos"
ACCOUNT_DIRNAME = "account"
USERS_DIRNAME = "users"
SETUP_CODE_FILENAME = "setup-code"
DATABASE_FILENAME = "hera.sqlite3"
MCP_FILENAME = "mcp.json"
CONFIG_FILENAME = "config.toml"
PERMISSIONS_FILENAME = "permissions.json"

__all__ = [
    "ACCOUNT_DIRNAME",
    "ARTIFACTS_DIRNAME",
    "CHATS_DIRNAME",
    "CONFIG_FILENAME",
    "DATABASE_FILENAME",
    "DEFAULT_HOME",
    "HOME_ENV",
    "LOGOS_DIRNAME",
    "MCP_FILENAME",
    "MEMORIES_DIRNAME",
    "MIND_DIRNAME",
    "PERMISSIONS_FILENAME",
    "SCRATCH_DIRNAME",
    "SETUP_CODE_FILENAME",
    "SKILLS_DIRNAME",
    "USERS_DIRNAME",
    "account_dir",
    "artifacts_dir",
    "avatar_path",
    "chat_dir",
    "chats_dir",
    "config_path",
    "database_path",
    "home",
    "logo_path",
    "logos_dir",
    "mcp_path",
    "memories_dir",
    "mind_dir",
    "permissions_path",
    "scratch_dir",
    "setup_code_path",
    "skills_dir",
    "user_dir",
    "user_memories_dir",
    "user_mind_dir",
    "user_permissions_path",
    "users_dir",
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


def account_dir() -> Path:
    """Where a single-user install kept its one avatar, before there were users.

    Read once, by the boot step that moves the file under the first admin's own directory, and
    by nothing else.
    """
    return home() / ACCOUNT_DIRNAME


def users_dir() -> Path:
    """What belongs to one person rather than to the instance, one directory each (ADR 28)."""
    return home() / USERS_DIRNAME


def user_dir(user_id: str) -> Path:
    """One person's directory, refused for anything that is not a single plain path segment —
    the same guard as :func:`chat_dir`, for the same reason."""
    if not user_id or user_id in {".", ".."} or "/" in user_id or "\\" in user_id:
        raise ValueError(f"not a usable user id: {user_id!r}")
    return users_dir() / user_id


def avatar_path(user_id: str) -> Path:
    """One person's avatar. One file with no extension: the media type is stored beside the
    user row, and a name with no extension is one nothing can be tricked into running."""
    return user_dir(user_id) / "avatar"


def user_mind_dir(user_id: str) -> Path:
    """One person's mind, cloned from the template in :func:`mind_dir` (ADR 28)."""
    return user_dir(user_id) / MIND_DIRNAME


def user_memories_dir(user_id: str) -> Path:
    """What she knows about one person — theirs alone, because every one is in the prompt."""
    return user_dir(user_id) / MEMORIES_DIRNAME


def user_permissions_path(user_id: str) -> Path:
    """One person's own permission rules, over the instance's :func:`permissions_path`."""
    return user_dir(user_id) / PERMISSIONS_FILENAME


def setup_code_path() -> Path:
    """Where a fresh install writes the code its setup wizard asks for, beside printing it.

    For whoever has a shell on the host and missed the log line. Deleted once somebody has
    claimed the instance.
    """
    return home() / SETUP_CODE_FILENAME


def logos_dir() -> Path:
    """Custom provider logos — one file per provider that uploaded one."""
    return home() / LOGOS_DIRNAME


def logo_path(provider_name: str) -> Path:
    """One provider's uploaded logo, named after it and nothing else.

    Guarded the same way ``chat_dir`` guards its id, even though ``hera_core`` already
    restricts a provider name to lowercase/digits/-/_ before this is ever called — defense in
    depth costs one more check.
    """
    bad = not provider_name or provider_name in {".", ".."}
    bad = bad or "/" in provider_name or "\\" in provider_name
    if bad:
        raise ValueError(f"not a usable provider name: {provider_name!r}")
    return logos_dir() / f"{provider_name}.logo"


def database_path() -> Path:
    """The SQLite file holding everything relational."""
    return home() / DATABASE_FILENAME


def mcp_path() -> Path:
    """The MCP server configuration, in the Claude-Desktop ``mcpServers`` shape."""
    return home() / MCP_FILENAME


def permissions_path() -> Path:
    """The rules a person has made or answered, over the ones Hera ships with."""
    return home() / PERMISSIONS_FILENAME


def config_path() -> Path:
    """Boot settings."""
    return home() / CONFIG_FILENAME

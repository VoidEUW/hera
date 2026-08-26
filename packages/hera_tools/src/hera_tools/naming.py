"""Namespacing tool names, so two servers cannot collide.

A tool is offered to the model as ``server__tool``. That single decision has to satisfy three
audiences at once: the model, which sees the name in a function schema and must be able to
repeat it exactly; :mod:`hera_permissions`, which matches ``fnmatch`` patterns like ``fs__*``
against it; and a person reading a permission dialogue, who should be able to tell where the
tool came from without being told.

The separator is a double underscore because a single one is common inside tool names and a
dot is not accepted by every endpoint's function-name validation.
"""

from __future__ import annotations

import re

from hera_tools.errors import InvalidToolName

SEPARATOR = "__"
"""Between the server name and the tool name."""

_SERVER_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
"""What a server may be called in ``mcp.json``.

Restrictive on purpose. The qualified name ends up as an OpenAI function name, where the
accepted alphabet is ``[a-zA-Z0-9_-]``; a server called ``my.server`` would produce a name some
endpoints reject and others silently rename, which is the worst of the two.
"""

MAX_NAME_LENGTH = 64
"""The limit OpenAI-compatible endpoints apply to a function name.

Exceeding it is a warning rather than an error: a local server may not check, and refusing to
expose an otherwise working tool because its name is long would be a strange trade. See
:func:`is_overlong`.
"""


def validate_server_name(server: str) -> str:
    """Check a server name and return it, or explain what is wrong with it."""
    if not _SERVER_PATTERN.match(server):
        raise InvalidToolName(
            f"invalid MCP server name {server!r}: use letters, digits, '-' and '_', "
            "starting with a letter or digit"
        )
    if SEPARATOR in server:
        raise InvalidToolName(
            f"invalid MCP server name {server!r}: {SEPARATOR!r} separates the server from the "
            "tool and cannot appear inside the server name"
        )
    return server


def qualify(server: str, tool: str) -> str:
    """Build the namespaced name a model is shown."""
    validate_server_name(server)
    if not tool:
        raise InvalidToolName(f"server {server!r} offered a tool with an empty name")
    return f"{server}{SEPARATOR}{tool}"


def split(qualified: str) -> tuple[str, str]:
    """Take a namespaced name apart again.

    Splits at the **first** separator, which is unambiguous precisely because
    :func:`validate_server_name` forbids one inside a server name -- a tool called
    ``read__file`` on server ``fs`` round-trips, where splitting at the last would not.
    """
    server, found, tool = qualified.partition(SEPARATOR)
    if not found or not server or not tool:
        raise InvalidToolName(
            f"{qualified!r} is not a namespaced tool name; expected 'server{SEPARATOR}tool'"
        )
    return server, tool


def is_overlong(qualified: str) -> bool:
    """Whether a name is longer than endpoints generally accept."""
    return len(qualified) > MAX_NAME_LENGTH

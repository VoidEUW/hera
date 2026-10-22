"""Adding, changing and removing MCP servers, and turning a tool on or off (#108).

What Settings → Servers does, in one place. A server change moves three things together -- the
file (``~/.hera/mcp.json``), the registry the turn is asking, and the orchestrator holding that
registry -- and the same lock that guards a permission change guards this, because both replace
``container.registry`` and a rule written while a server was being swapped in would otherwise be
lost to whichever finished last.

A tool is turned off by a rule, not by anything new: ``deny`` on ``server__tool``, through
:mod:`hera_core.rulebook`, which also keeps it across a restart (ADR 23). The turn does not offer
a tool the policy denies, so off means she does not have it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from hera_core import permission_rules, rulebook
from hera_core.rulebook import NoToolLayer
from hera_permissions import Decision
from hera_tools import (
    ManagedServer,
    McpConfig,
    ToolRegistry,
    merge,
    put_server,
    qualify,
    raw_servers,
    remove_server,
)

if TYPE_CHECKING:
    from hera_core.wiring import Services

__all__ = [
    "BuiltInServer",
    "NoSuchServer",
    "NoToolLayer",
    "ToolState",
    "close",
    "declared",
    "remove",
    "save",
    "set_allowed",
    "tool_state",
]

OFF = "Off on the Servers screen"
ON = "On from the Servers screen"
"""What the rule a checkbox writes is called on the Permissions screen."""


class NoSuchServer(LookupError):
    """``mcp.json`` has no server by that name."""


class BuiltInServer(ValueError):
    """A server Hera mounts herself. It is not in the file and is not the file's to change."""


class ToolState(BaseModel):
    """Whether a tool is on, and which rule says so when it is off."""

    model_config = ConfigDict(frozen=True)

    allowed: bool
    rule: str | None = None
    """The pattern of the rule that decided it, if any rule did."""

    exact: bool = False
    """Whether that rule is on this one tool, rather than a wider pattern covering it."""


def declared(container: Services) -> dict[str, dict[str, Any]]:
    """The entries as written -- unexpanded, secrets and all. Never leaves the server as is."""
    return raw_servers(_registry(container).settings.resolved_config_path())


def save(
    container: Services, name: str, submitted: Mapping[str, Any]
) -> tuple[bool, tuple[ManagedServer, ...]]:
    """Add a server or replace one, and reconnect only what changed.

    ``submitted`` is what a form edits; anything else already in the entry is kept (see
    :func:`hera_tools.merge`). Returns whether the server is new, and the servers the swap
    retired -- for the caller to :func:`close`, once this has returned and nothing here holds
    the lock.
    """
    registry = _registry(container)
    if name in registry.builtin_names:
        raise BuiltInServer(name)
    path = registry.settings.resolved_config_path()
    with permission_rules.LOCK:
        entry = merge(raw_servers(path).get(name), submitted)
        existed = put_server(path, name, entry)
        return not existed, _apply(container, path)


def remove(container: Services, name: str) -> tuple[ManagedServer, ...]:
    """Take a server out of the file and stop it."""
    registry = _registry(container)
    if name in registry.builtin_names:
        raise BuiltInServer(name)
    path = registry.settings.resolved_config_path()
    with permission_rules.LOCK:
        if not remove_server(path, name):
            raise NoSuchServer(name)
        return _apply(container, path)


async def close(retired: Sequence[ManagedServer]) -> None:
    """Stop servers the registry no longer has. A failure to close one is not worth reporting."""
    await asyncio.gather(*(server.aclose() for server in retired), return_exceptions=True)


def tool_state(container: Services, tool: str) -> ToolState:
    """Whether ``tool`` is on, as the turn would see it."""
    outcome = _registry(container).check(tool)
    rule = outcome.rule.pattern if outcome.rule is not None else None
    return ToolState(
        allowed=outcome.decision is not Decision.DENY,
        rule=rule,
        exact=rule == tool,
    )


def set_allowed(container: Services, server: str, local_name: str, allowed: bool) -> ToolState:
    """Turn a tool on or off by writing the rule that says so.

    Off is a ``deny`` on exactly this tool. On removes that rule -- and when a wider one still
    says no (``fs__*``), writes an exact ``allow`` beside it, which wins by being more specific
    and leaves the wide rule to keep covering the rest.
    """
    tool = qualify(server, local_name)
    registry = _registry(container)
    exact = registry.policy.base.get(tool)

    if not allowed:
        if tool_state(container, tool).allowed:
            if exact is None:
                rulebook.add(container, pattern=tool, decision=Decision.DENY, name=OFF)
            else:
                rulebook.change(container, tool, decision=Decision.DENY, name=OFF)
        return tool_state(container, tool)

    if not tool_state(container, tool).allowed:
        if exact is not None and exact.decision is Decision.DENY:
            try:
                rulebook.remove(container, tool)
            except rulebook.BuiltInRule:
                rulebook.change(container, tool, decision=Decision.ALLOW, name=ON)
        if not tool_state(container, tool).allowed:
            rulebook.add(container, pattern=tool, decision=Decision.ALLOW, name=ON)
    return tool_state(container, tool)


def _apply(container: Services, path: Path) -> tuple[ManagedServer, ...]:
    """Read the file as it now is and swap the registry to match. Call under the lock."""
    registry = _registry(container)
    swapped, retired = registry.with_config(McpConfig.load(path))
    container.registry = swapped
    container.orchestrator.registry = swapped
    return retired


def _registry(container: Services) -> ToolRegistry:
    if container.registry is None:
        raise NoToolLayer
    return container.registry

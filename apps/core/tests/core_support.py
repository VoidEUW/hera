"""Helpers the application suite imports by name.

Not in `conftest.py`: mypy is configured to skip those, because two packages' conftests resolve
to one module name and it has no by-path loading the way pytest does.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

from httpx import Response

from hera_permissions import Decision, Outcome, Policy
from hera_tools import Catalogue, Failure, Tool, ToolInvocation, ToolResult

API = "/api/v1"
"""The versioned prefix every route sits under (ADR 6)."""


class WriteSkill(Protocol):
    """Writes a skill directory under the temporary skills path and returns it."""

    def __call__(self, skill_id: str, *, description: str = ..., body: str = ...) -> Path: ...


class StubTools:
    """A tool layer with scripted answers, satisfying ``hera_chats.ports.Tools``."""

    def __init__(
        self,
        *,
        tools: Sequence[str] = ("fs__read_file",),
        policy: Policy | None = None,
    ) -> None:
        self.catalogue_value = Catalogue.of(
            Tool(
                name=name,
                server=name.split("__")[0],
                local_name=name.split("__")[-1],
                description=f"does {name}",
            )
            for name in tools
        )
        self._policy = policy or Policy(fallback=Decision.ALLOW)
        self.dispatched: list[list[ToolInvocation]] = []

    @property
    def policy(self) -> Policy:
        return self._policy

    def with_policy(self, policy: Policy) -> StubTools:
        replacement = StubTools(policy=policy)
        replacement.catalogue_value = self.catalogue_value
        replacement.dispatched = self.dispatched
        return replacement

    def check(self, tool: str, *, profile: str | None = None) -> Outcome:
        return self._policy.check(tool, profile=profile)

    async def catalogue(self, *, refresh: bool = False) -> Catalogue:
        return self.catalogue_value

    async def status(self) -> tuple[Any, ...]:
        from hera_tools import ServerStatus

        return (ServerStatus(name="fs", connected=True, tools=len(self.catalogue_value)),)

    async def dispatch_all(
        self,
        invocations: Iterable[ToolInvocation],
        *,
        profile: str | None = None,
        confirmed: Sequence[str] = (),
    ) -> list[ToolResult]:
        calls = list(invocations)
        self.dispatched.append(calls)
        return [self._answer(call) for call in calls]

    async def aclose(self) -> None:
        return None

    def _answer(self, call: ToolInvocation) -> ToolResult:
        outcome = self._policy.check(call.tool)
        if outcome.decision is Decision.DENY:
            return ToolResult.failed(
                call_id=call.call_id,
                tool=call.tool,
                failure=Failure.DENIED,
                text=f"not allowed — {outcome.reason}",
            )
        return ToolResult(call_id=call.call_id, tool=call.tool, text=f"ran {call.tool}")


def sse(response: Response) -> list[tuple[str, Any]]:
    """Parse a Server-Sent Events body into ``(event name, payload)`` pairs.

    Written out rather than pulled from a library because it is the thing under test: if the
    framing is wrong, a parser that is lenient about it would hide exactly the bug worth
    catching.
    """
    frames: list[tuple[str, Any]] = []
    for block in response.text.split("\n\n"):
        if not block.strip():
            continue
        name = ""
        data: list[str] = []
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data.append(line.removeprefix("data: "))
        frames.append((name, json.loads("\n".join(data))))
    return frames


def names(frames: Sequence[tuple[str, Any]]) -> list[str]:
    return [name for name, _ in frames]


def payload(frames: Sequence[tuple[str, Any]], name: str) -> Any:
    """The first payload of one event name."""
    for found, body in frames:
        if found == name:
            return body
    raise AssertionError(f"no {name!r} frame in {names(frames)}")

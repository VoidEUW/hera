"""Types and helpers the chats fixtures hand out.

Not in `conftest.py` because mypy is configured to skip those — two packages' conftests resolve
to one module name, and mypy has no by-path loading the way pytest does. Anything a test needs
to import by name lives here instead.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Sequence
from pathlib import Path
from typing import Protocol

from hera_chats.events import ChatEvent

from hera_permissions import Decision, Outcome, Policy
from hera_tools import Catalogue, Failure, Tool, ToolInvocation, ToolResult


class WriteSkill(Protocol):
    """Writes a skill directory under the temporary skills path and returns it."""

    def __call__(self, skill_id: str, *, description: str = ..., body: str = ...) -> Path: ...


async def drain(stream: AsyncIterator[ChatEvent]) -> list[ChatEvent]:
    """Consume a turn to the end."""
    return [event async for event in stream]


def kinds(events: Sequence[ChatEvent]) -> list[str]:
    """The ``type`` of each event, which is what most assertions here are about."""
    return [event.type for event in events]


class StubTools:
    """A tool layer with scripted answers.

    Satisfies ``hera_chats.ports.Tools`` structurally, which is what that protocol is for: a
    turn uses three methods, and standing up MCP servers to exercise ordering and refusals
    would be testing the servers rather than the loop.
    """

    def __init__(
        self,
        *,
        tools: Sequence[str] = ("fs__read_file",),
        policy: Policy | None = None,
        results: dict[str, ToolResult] | None = None,
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
        self.policy = policy or Policy(fallback=Decision.ALLOW)
        self.results = results or {}
        self.dispatched: list[list[ToolInvocation]] = []
        self.confirmed_seen: list[tuple[str, ...]] = []

    def check(self, tool: str, *, profile: str | None = None) -> Outcome:
        return self.policy.check(tool, profile=profile)

    async def catalogue(self, *, refresh: bool = False) -> Catalogue:
        return self.catalogue_value

    async def dispatch_all(
        self,
        invocations: Iterable[ToolInvocation],
        *,
        profile: str | None = None,
        confirmed: Sequence[str] = (),
    ) -> list[ToolResult]:
        calls = list(invocations)
        self.dispatched.append(calls)
        self.confirmed_seen.append(tuple(confirmed))
        return [self._answer(call) for call in calls]

    def _answer(self, call: ToolInvocation) -> ToolResult:
        scripted = self.results.get(call.tool)
        if scripted is not None:
            return scripted.model_copy(update={"call_id": call.call_id})
        if self.policy.check(call.tool).decision is Decision.DENY:
            return ToolResult.failed(
                call_id=call.call_id,
                tool=call.tool,
                failure=Failure.DENIED,
                text=f"not allowed — {self.policy.check(call.tool).reason}",
            )
        return ToolResult(call_id=call.call_id, tool=call.tool, text=f"ran {call.tool}")

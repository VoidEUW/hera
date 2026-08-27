"""What a turn needs from the tool layer, expressed as a protocol.

``hera_tools.ToolRegistry`` satisfies this exactly and is what the application passes. The
protocol exists anyway, for two reasons.

It says what the turn actually uses — three methods out of a much larger class — so reading
this file tells you the whole of the coupling. And it lets a test drive the tool loop with a
handful of scripted results instead of standing up MCP servers, which matters because the
things worth testing here are *ordering* and *what happens when a call is refused*, and neither
of those is about a real server.

Note the asymmetry with ``hera_tools.ports``: those exist because that package **may not**
import what it needs. This one may — the layering table allows it — and does, for the concrete
type in the application. That is the difference between a port that inverts a dependency and
one that narrows it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, runtime_checkable

from hera_permissions import Outcome
from hera_tools import Catalogue, ToolInvocation, ToolResult


@runtime_checkable
class Tools(Protocol):
    """The slice of ``hera_tools.ToolRegistry`` a turn touches."""

    def check(self, tool: str, *, profile: str | None = None) -> Outcome:
        """Ask the policy without running anything.

        Separate from dispatch because an ``ask`` needs a person, and that round trip belongs
        to whoever owns the conversation.
        """
        ...

    async def catalogue(self, *, refresh: bool = False) -> Catalogue:
        """Every tool currently on offer, from every reachable server."""
        ...

    async def dispatch_all(
        self,
        invocations: Iterable[ToolInvocation],
        *,
        profile: str | None = None,
        confirmed: Sequence[str] = (),
    ) -> list[ToolResult]:
        """Run several calls at once. Parallel is the point — see ADR 3."""
        ...

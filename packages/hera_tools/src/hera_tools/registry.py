"""Every server at once: one catalogue, one permission check, one place calls go through.

This is the object the turn holds. It knows which servers exist, what they offer under which
namespaced name, and whether a given call is allowed to happen -- and it is the boundary where
failure stops being an exception. Above this line every call produces a
:class:`~hera_tools.results.ToolResult`, including the ones that were refused, misnamed, or
sent to a server that is not running. Below it, things raise.

That asymmetry is the whole design. A turn that has to catch four kinds of tool failure ends up
deciding what to do about each, and the answer is always the same: tell the model, keep going.
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import time
from collections.abc import Iterable, Mapping, Sequence

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, ConfigDict

from hera_permissions import Decision, Outcome, Policy
from hera_tools.catalogue import Catalogue, Tool
from hera_tools.config import McpConfig
from hera_tools.errors import ServerUnavailable, ToolTimeout
from hera_tools.results import Failure, ToolInvocation, ToolResult
from hera_tools.server import ManagedServer
from hera_tools.settings import ToolsSettings

logger = logging.getLogger(__name__)

_SUGGESTIONS = 3


class ServerStatus(BaseModel):
    """What to show on a settings page, and in the log line when a turn found no tools."""

    model_config = ConfigDict(frozen=True)

    name: str
    connected: bool
    tools: int
    failure: str | None = None


class ToolRegistry:
    """The tool layer, assembled."""

    def __init__(self, servers: Sequence[ManagedServer], *, policy: Policy | None = None) -> None:
        self._servers = tuple(servers)
        self._policy = policy or Policy()
        """No policy means the default: every tool asks. A registry built without one is not
        an open door."""

    @classmethod
    def from_config(
        cls,
        config: McpConfig,
        *,
        policy: Policy | None = None,
        builtin: MCPServer | None = None,
        settings: ToolsSettings | None = None,
    ) -> ToolRegistry:
        """Build from a parsed ``mcp.json``, with an in-process server alongside the rest.

        ``builtin`` is a server object, not a flag, and this package does not know what is on
        it: Hera's own four tools live in ``hera_mcp``, which sits below this one and is wired
        by the application because it needs the memory, note and skill ports. It is mounted
        under **its own** ``name``, so the word "hera" is written in one place rather than
        agreed on by two packages. ``None`` mounts nothing, which is a legitimate configuration
        for a test and for a deployment that only wants somebody else's servers.
        """
        settings = settings or ToolsSettings()
        servers = [
            ManagedServer.from_config(name, server, settings)
            for name, server in config.enabled().items()
        ]
        if builtin is not None:
            servers.insert(0, ManagedServer.in_process(builtin.name, builtin, settings))
        return cls(servers, policy=policy)

    @classmethod
    def open(
        cls,
        *,
        policy: Policy | None = None,
        settings: ToolsSettings | None = None,
        builtin: MCPServer | None = None,
    ) -> ToolRegistry:
        """Read ``mcp.json`` from disk and build. The application's one-liner at startup.

        ``builtin`` left out means the configured servers and nothing else. It used to default
        to an unwired copy of her own server; a default that quietly mounts four tools is the
        kind of thing you discover from a catalogue listing rather than from the call site.
        """
        settings = settings or ToolsSettings()
        return cls.from_config(
            McpConfig.load(settings.resolved_config_path()),
            policy=policy,
            builtin=builtin,
            settings=settings,
        )

    @property
    def policy(self) -> Policy:
        return self._policy

    def with_policy(self, policy: Policy) -> ToolRegistry:
        """The same servers, a different policy.

        Shares the servers rather than reconnecting them: answering a confirmation with
        "always allow" produces a new policy, and paying for four subprocess restarts to
        honour it would be absurd.
        """
        return ToolRegistry(self._servers, policy=policy)

    # -- what exists -------------------------------------------------------------------

    async def catalogue(self, *, refresh: bool = False) -> Catalogue:
        """Every tool from every server that answers.

        Servers are asked in parallel and a server that fails contributes nothing. This is
        where ADR 4's "an unreachable server degrades to a missing tool" actually happens: the
        turn is built from what came back, and nothing waits on what did not.
        """
        listings = await asyncio.gather(
            *(server.tools(refresh=refresh) for server in self._servers),
            return_exceptions=True,
        )

        tools: list[Tool] = []
        for server, listing in zip(self._servers, listings, strict=True):
            if isinstance(listing, BaseException):
                logger.info("skipping tools from %s: %s", server.name, listing)
                continue
            tools.extend(listing)
        return Catalogue.of(tools)

    async def status(self) -> tuple[ServerStatus, ...]:
        """One line per server, for a settings page or a startup log."""
        catalogue = await self.catalogue()
        return tuple(
            ServerStatus(
                name=server.name,
                connected=server.connected,
                tools=len(catalogue.for_server(server.name)),
                failure=server.failure,
            )
            for server in self._servers
        )

    # -- what may run ------------------------------------------------------------------

    def check(self, tool: str, *, profile: str | None = None) -> Outcome:
        """Ask the policy, without running anything.

        The turn calls this first, because an ``ask`` outcome needs a person and that round
        trip belongs to whoever owns the conversation, not here.
        """
        return self._policy.check(tool, profile=profile)

    # -- running it --------------------------------------------------------------------

    async def dispatch(
        self,
        invocation: ToolInvocation,
        *,
        profile: str | None = None,
        confirmed: bool = False,
        context: Mapping[str, str] | None = None,
    ) -> ToolResult:
        """Check, dispatch, and answer -- with a result whatever happens.

        ``confirmed`` is the answer to an ``ask``: the person said yes to this one call, so
        the check is satisfied without the policy having changed. A ``deny`` is still a deny;
        a confirmation cannot overrule a rule that says no.

        ``context`` is what the caller knows about the situation and the model does not -- which
        conversation this is, in practice. It travels in the request's ``_meta`` (ADR 12) and
        this package does not read it: like ``builtin``, it is something the application filled
        in and this one only carries. It goes to **every** server, including foreign ones, which
        is deliberate -- the keys are namespaced and a server that does not know them ignores
        them, and the alternative is this package learning which servers are Hera's.
        """
        started = time.monotonic()
        outcome = self.check(invocation.tool, profile=profile)

        if refusal := _refusal(invocation, outcome, confirmed=confirmed):
            return refusal

        catalogue = await self.catalogue()
        tool = catalogue.get(invocation.tool)
        if tool is None:
            return ToolResult.failed(
                call_id=invocation.call_id,
                tool=invocation.tool,
                failure=Failure.UNKNOWN_TOOL,
                text=_unknown_tool_text(invocation.tool, catalogue),
                duration_ms=_elapsed_ms(started),
            )

        server = self._server(tool.server)
        try:
            result = await server.call(tool.local_name, invocation.arguments, context=context)
        except ToolTimeout as exc:
            return ToolResult.failed(
                call_id=invocation.call_id,
                tool=invocation.tool,
                failure=Failure.TIMEOUT,
                text=f"the call timed out after {exc.timeout_s:g}s and was abandoned",
                duration_ms=_elapsed_ms(started),
            )
        except Exception as exc:
            reason = exc.reason if isinstance(exc, ServerUnavailable) else str(exc)
            logger.warning("tool %s failed: %s", invocation.tool, reason)
            return ToolResult.failed(
                call_id=invocation.call_id,
                tool=invocation.tool,
                failure=Failure.UNAVAILABLE,
                text=f"the tool could not be run: {reason}",
                duration_ms=_elapsed_ms(started),
            )

        return ToolResult.from_call(
            call_id=invocation.call_id,
            tool=invocation.tool,
            result=result,
            duration_ms=_elapsed_ms(started),
        )

    async def dispatch_all(
        self,
        invocations: Iterable[ToolInvocation],
        *,
        profile: str | None = None,
        confirmed: Sequence[str] = (),
        context: Mapping[str, str] | None = None,
    ) -> list[ToolResult]:
        """Run several calls at once, in the order they were given.

        Parallel is the point. The target model emits parallel tool calls and several
        independent ones in a round is the everyday case; running them one after another would
        turn one round-trip into four.

        ``confirmed`` lists the call ids a person has just approved. ``context`` is the same for
        every call in the batch, because it describes the turn rather than the call.
        """
        approved = set(confirmed)
        calls = list(invocations)
        return list(
            await asyncio.gather(
                *(
                    self.dispatch(
                        call,
                        profile=profile,
                        confirmed=call.call_id in approved,
                        context=context,
                    )
                    for call in calls
                )
            )
        )

    async def aclose(self) -> None:
        """Close every server. Safe to call twice."""
        await asyncio.gather(*(server.aclose() for server in self._servers), return_exceptions=True)

    def _server(self, name: str) -> ManagedServer:
        server = next((s for s in self._servers if s.name == name), None)
        if server is None:  # pragma: no cover -- a catalogue entry names a server we own
            raise ServerUnavailable(name, "no such server in this registry")
        return server


def _refusal(invocation: ToolInvocation, outcome: Outcome, *, confirmed: bool) -> ToolResult | None:
    """The permission answer, as a result the model can read -- or ``None`` to go ahead."""
    if outcome.decision is Decision.ALLOW:
        return None
    if outcome.decision is Decision.ASK and confirmed:
        return None

    if outcome.decision is Decision.DENY:
        text = "that tool is not allowed here"
    else:
        text = "that tool needs the person's confirmation, which was not given"
    if outcome.reason:
        text = f"{text}: {outcome.reason}"

    return ToolResult.failed(
        call_id=invocation.call_id,
        tool=invocation.tool,
        failure=Failure.DENIED,
        text=text,
    )


def _unknown_tool_text(tool: str, catalogue: Catalogue) -> str:
    """Say what was asked for and what exists, because a model given both corrects itself."""
    close = difflib.get_close_matches(tool, catalogue.names(), n=_SUGGESTIONS, cutoff=0.6)
    if close:
        return f"there is no tool named {tool!r}. Did you mean: {', '.join(close)}?"
    return f"there is no tool named {tool!r}."


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)

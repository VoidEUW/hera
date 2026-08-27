"""The registry: one catalogue, the permission gate, and failure that never raises.

The rule under test throughout is the one from the module docstring -- above this boundary,
every call produces a result. There is no test here for an exception escaping ``dispatch``,
because there is no way to make one.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from hera_tools.config import McpConfig, StdioServer
from hera_tools.registry import ToolRegistry
from hera_tools.results import Failure, ToolInvocation
from hera_tools.server import ManagedServer
from mcp.server.mcpserver import MCPServer
from tools_support import STDIO_SERVER_SOURCE

from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_tools import ToolsSettings


def _emotion(call_id: str = "c1", kind: str = "curious") -> ToolInvocation:
    return ToolInvocation(call_id=call_id, tool="toy__emotion", arguments={"kind": kind})


class TestPermission:
    async def test_an_allowed_tool_runs(self, registry: ToolRegistry) -> None:
        assert (await registry.dispatch(_emotion())).ok

    async def test_a_denied_tool_does_not(self, toy: MCPServer, settings: ToolsSettings) -> None:
        registry = ToolRegistry(
            [ManagedServer.in_process("toy", toy, settings)],
            policy=Policy(
                base=PermissionSet(
                    rules=[
                        Rule(
                            pattern="toy__emotion",
                            decision=Decision.DENY,
                            reason="not in this profile",
                        )
                    ]
                )
            ),
        )

        result = await registry.dispatch(_emotion())

        assert not result.ok
        assert result.failure is Failure.DENIED
        assert "not in this profile" in result.text
        await registry.aclose()

    async def test_the_default_policy_asks_and_therefore_refuses(
        self, toy: MCPServer, settings: ToolsSettings
    ) -> None:
        """A registry built without a policy is not an open door."""
        registry = ToolRegistry([ManagedServer.in_process("toy", toy, settings)])

        result = await registry.dispatch(_emotion())

        assert result.failure is Failure.DENIED
        assert "confirmation" in result.text
        await registry.aclose()

    async def test_a_confirmed_call_runs(self, toy: MCPServer, settings: ToolsSettings) -> None:
        """The person said yes to this one call; the policy itself has not changed."""
        registry = ToolRegistry([ManagedServer.in_process("toy", toy, settings)])

        assert (await registry.dispatch(_emotion(), confirmed=True)).ok
        assert registry.check("toy__emotion").decision is Decision.ASK
        await registry.aclose()

    async def test_a_confirmation_cannot_overrule_a_deny(
        self, toy: MCPServer, settings: ToolsSettings
    ) -> None:
        registry = ToolRegistry(
            [ManagedServer.in_process("toy", toy, settings)],
            policy=Policy(base=PermissionSet.of(deny=["*"])),
        )

        result = await registry.dispatch(_emotion(), confirmed=True)

        assert result.failure is Failure.DENIED
        await registry.aclose()

    async def test_a_profile_is_passed_through(
        self, toy: MCPServer, settings: ToolsSettings
    ) -> None:
        registry = ToolRegistry(
            [ManagedServer.in_process("toy", toy, settings)],
            policy=Policy(profiles={"coding": PermissionSet.of(allow=["toy__*"])}),
        )

        assert (await registry.dispatch(_emotion(), profile="coding")).ok
        assert not (await registry.dispatch(_emotion())).ok
        await registry.aclose()

    async def test_answering_a_confirmation_produces_a_registry_that_shares_the_servers(
        self, registry: ToolRegistry
    ) -> None:
        """ "Always allow" must not cost a round of subprocess restarts."""
        await registry.catalogue()
        loosened = registry.with_policy(
            registry.policy.with_rule(Rule(pattern="toy__note", decision=Decision.DENY))
        )

        assert (await loosened.dispatch(_emotion())).ok
        assert loosened.check("toy__note").decision is Decision.DENY
        assert registry.check("toy__note").decision is Decision.ALLOW


class TestUnknownTools:
    async def test_a_name_nobody_has(self, registry: ToolRegistry) -> None:
        result = await registry.dispatch(ToolInvocation(call_id="c1", tool="fs__read"))
        assert result.failure is Failure.UNKNOWN_TOOL
        assert "fs__read" in result.text

    async def test_a_near_miss_is_suggested(self, registry: ToolRegistry) -> None:
        """A model given the right name next to the wrong one corrects itself."""
        result = await registry.dispatch(ToolInvocation(call_id="c1", tool="toy__emotions"))
        assert "toy__emotion" in result.text

    async def test_a_name_that_is_not_namespaced_at_all(self, registry: ToolRegistry) -> None:
        result = await registry.dispatch(ToolInvocation(call_id="c1", tool="emotion"))
        assert result.failure is Failure.UNKNOWN_TOOL


class TestDegrading:
    async def test_an_unreachable_server_contributes_no_tools(
        self, toy: MCPServer, allow_everything: Policy, settings: ToolsSettings
    ) -> None:
        """ADR 4, the whole promise: a broken server is a missing tool, not a broken turn."""
        registry = ToolRegistry(
            [
                ManagedServer.in_process("toy", toy, settings),
                ManagedServer.from_config(
                    "ghost", StdioServer(command="no-such-command"), settings
                ),
            ],
            policy=allow_everything,
        )

        catalogue = await registry.catalogue()

        assert len(catalogue.for_server("ghost")) == 0
        assert len(catalogue.for_server("toy")) == 2
        assert (await registry.dispatch(_emotion())).ok
        await registry.aclose()

    async def test_status_says_why(
        self, toy: MCPServer, allow_everything: Policy, settings: ToolsSettings
    ) -> None:
        registry = ToolRegistry(
            [
                ManagedServer.in_process("toy", toy, settings),
                ManagedServer.from_config(
                    "ghost", StdioServer(command="no-such-command"), settings
                ),
            ],
            policy=allow_everything,
        )

        status = {server.name: server for server in await registry.status()}

        assert status["toy"].connected
        assert status["toy"].tools == 2
        assert not status["ghost"].connected
        assert status["ghost"].failure
        await registry.aclose()

    async def test_a_call_to_a_server_that_will_not_start(
        self, allow_everything: Policy, settings: ToolsSettings
    ) -> None:
        """The tool is in no catalogue, so this is an unknown tool rather than a crash."""
        registry = ToolRegistry(
            [ManagedServer.from_config("ghost", StdioServer(command="no-such"), settings)],
            policy=allow_everything,
        )

        result = await registry.dispatch(ToolInvocation(call_id="c1", tool="ghost__echo"))

        assert result.failure is Failure.UNKNOWN_TOOL
        await registry.aclose()

    async def test_a_server_that_dies_between_the_listing_and_the_call(
        self, allow_everything: Policy, settings: ToolsSettings
    ) -> None:
        """The catalogue is real, the server is gone, and the answer is still a result."""
        registry = ToolRegistry(
            [
                ManagedServer.from_config(
                    "spike",
                    StdioServer(command=sys.executable, args=["-c", STDIO_SERVER_SOURCE]),
                    settings,
                )
            ],
            policy=allow_everything,
        )
        assert "spike__die" in await registry.catalogue()

        result = await registry.dispatch(ToolInvocation(call_id="c1", tool="spike__die"))

        assert result.failure is Failure.UNAVAILABLE
        assert "could not be run" in result.text
        await registry.aclose()

    async def test_a_call_that_takes_too_long(
        self, allow_everything: Policy, settings: ToolsSettings
    ) -> None:
        server: MCPServer = MCPServer("slow", version="0.1.0")

        @server.tool(description="Take a while.")
        async def wait() -> str:
            await asyncio.sleep(5)
            return "done"

        managed = ManagedServer.in_process("slow", server, settings)
        managed._call_timeout_s = 0.05
        registry = ToolRegistry([managed], policy=allow_everything)

        result = await registry.dispatch(ToolInvocation(call_id="c1", tool="slow__wait"))

        assert result.failure is Failure.TIMEOUT
        assert "timed out" in result.text
        await registry.aclose()


class TestParallelDispatch:
    async def test_results_come_back_in_the_order_they_were_given(
        self, registry: ToolRegistry
    ) -> None:
        calls = [_emotion(call_id=f"c{n}", kind=f"k{n}") for n in range(4)]

        results = await registry.dispatch_all(calls)

        assert [result.call_id for result in results] == ["c0", "c1", "c2", "c3"]
        assert all(result.ok for result in results)

    async def test_one_bad_call_does_not_take_the_others_down(self, registry: ToolRegistry) -> None:
        """The same rule as ``ToolCallReady.parse_error`` in ``hera_providers``."""
        results = await registry.dispatch_all(
            [_emotion(call_id="good"), ToolInvocation(call_id="bad", tool="toy__nope")]
        )

        assert [result.ok for result in results] == [True, False]

    async def test_only_the_confirmed_calls_are_confirmed(
        self, toy: MCPServer, settings: ToolsSettings
    ) -> None:
        registry = ToolRegistry([ManagedServer.in_process("toy", toy, settings)])

        results = await registry.dispatch_all(
            [_emotion(call_id="yes"), _emotion(call_id="no")], confirmed=["yes"]
        )

        assert [result.ok for result in results] == [True, False]
        await registry.aclose()


class TestBuilding:
    async def test_from_config_mounts_the_in_process_server_first(
        self, toy: MCPServer, allow_everything: Policy, settings: ToolsSettings
    ) -> None:
        """Under its own name: this package does not know what it was handed, so it asks the
        server object rather than agreeing on a constant with whoever built it."""
        registry = ToolRegistry.from_config(
            McpConfig.parse(
                {"mcpServers": {"off": {"command": "no-such-command", "enabled": False}}}
            ),
            policy=allow_everything,
            builtin=toy,
            settings=settings,
        )

        status = await registry.status()

        assert [server.name for server in status] == ["toy"]
        await registry.aclose()

    async def test_without_a_builtin_nothing_is_mounted_in_process(
        self, allow_everything: Policy, settings: ToolsSettings
    ) -> None:
        registry = ToolRegistry.from_config(McpConfig(), policy=allow_everything, settings=settings)
        assert len(await registry.catalogue()) == 0
        await registry.aclose()

    async def test_open_reads_the_configured_file(
        self, tmp_path: Path, toy: MCPServer, allow_everything: Policy
    ) -> None:
        path = tmp_path / "mcp.json"
        path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "spike": {"command": sys.executable, "args": ["-c", STDIO_SERVER_SOURCE]}
                    }
                }
            ),
            encoding="utf-8",
        )
        settings = ToolsSettings(config_path=path, retry_after_s=0.0)

        registry = ToolRegistry.open(policy=allow_everything, settings=settings, builtin=toy)

        catalogue = await registry.catalogue()
        assert "spike__echo" in catalogue
        assert "toy__emotion" in catalogue
        await registry.aclose()

    async def test_closing_a_registry_that_never_connected_is_fine(
        self, allow_everything: Policy, settings: ToolsSettings
    ) -> None:
        registry = ToolRegistry.from_config(McpConfig(), policy=allow_everything, settings=settings)
        await registry.aclose()


class TestSettings:
    def test_the_default_path_follows_hera_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERA_HOME", "/tmp/hera-home")
        assert ToolsSettings().resolved_config_path() == Path("/tmp/hera-home/mcp.json")

    def test_an_explicit_path_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERA_HOME", "/tmp/hera-home")
        settings = ToolsSettings(config_path=Path("/elsewhere/mcp.json"))
        assert settings.resolved_config_path() == Path("/elsewhere/mcp.json")

    def test_hera_home_expands_a_tilde(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HERA_HOME", raising=False)
        assert ToolsSettings().resolved_config_path().is_absolute()

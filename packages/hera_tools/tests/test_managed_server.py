"""One server's lifecycle: lazy, concurrent, and survivable.

The stdio tests launch a real subprocess with the interpreter running the suite. They are the
only place the transport, the handshake and the process teardown are exercised together, and
they cost about a second between them -- worth it for the one part of this package that cannot
be reasoned about from the types.
"""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Any

import pytest
from hera_tools.config import StdioServer
from hera_tools.errors import ServerUnavailable, ToolTimeout
from hera_tools.server import ManagedServer, _describe, _settle
from mcp.client import Client
from mcp.server.mcpserver import MCPServer
from mcp.shared.exceptions import MCPError

from hera_tools import ToolsSettings


class _RefusingOpener(AbstractAsyncContextManager[Client]):
    """A connection that fails the way a missing executable does."""

    def __init__(self, error: BaseException) -> None:
        self.error = error

    async def __aenter__(self) -> Client:
        raise self.error

    async def __aexit__(self, *exc_info: Any) -> bool:
        return False


def _slow_server() -> MCPServer:
    server: MCPServer = MCPServer("slow", version="0.1.0")

    @server.tool(description="Take a while.")
    async def wait(seconds: float) -> str:
        await asyncio.sleep(seconds)
        return "done"

    return server


class TestInProcess:
    async def test_it_connects_on_first_use(self, toy: MCPServer) -> None:
        server = ManagedServer.in_process("toy", toy)
        assert not server.connected

        tools = await server.tools()

        assert server.connected
        assert "toy__emotion" in {tool.name for tool in tools}
        await server.aclose()

    async def test_the_listing_is_cached(self, toy: MCPServer) -> None:
        server = ManagedServer.in_process("toy", toy)
        first = await server.tools()
        assert await server.tools() is first
        assert await server.tools(refresh=True) == first
        await server.aclose()

    async def test_parallel_calls_to_one_server(self, toy: MCPServer) -> None:
        """A turn's worth of emotions is one round trip only if these overlap (ADR 3)."""
        server = ManagedServer.in_process("toy", toy)
        results = await asyncio.gather(
            *(server.call("emotion", {"kind": "curious", "text": str(n)}) for n in range(5))
        )
        assert [result.is_error for result in results] == [False] * 5
        await server.aclose()

    async def test_one_connection_for_concurrent_first_calls(self, toy: MCPServer) -> None:
        """Three cold calls must not race into three connections."""
        server = ManagedServer.in_process("toy", toy)
        await asyncio.gather(*(server.tools() for _ in range(3)))
        assert server.connected
        await server.aclose()

    async def test_closing_twice_is_harmless(self, toy: MCPServer) -> None:
        server = ManagedServer.in_process("toy", toy)
        await server.tools()
        await server.aclose()
        await server.aclose()
        assert not server.connected

    async def test_a_closed_server_refuses_rather_than_reconnects(self, toy: MCPServer) -> None:
        server = ManagedServer.in_process("toy", toy)
        await server.aclose()
        with pytest.raises(ServerUnavailable, match="closed"):
            await server.tools()


class TestTimeouts:
    async def test_a_slow_call_is_abandoned(self) -> None:
        server = ManagedServer(
            "slow", lambda: Client(server=_slow_server()), call_timeout_s=0.05, retry_after_s=0.0
        )
        with pytest.raises(ToolTimeout, match="slow: wait"):
            await server.call("wait", {"seconds": 5})
        await server.aclose()

    async def test_the_server_stays_usable_afterwards(self) -> None:
        """A timeout is one call giving up, not the connection dying."""
        server = ManagedServer(
            "slow", lambda: Client(server=_slow_server()), call_timeout_s=0.2, retry_after_s=0.0
        )
        with pytest.raises(ToolTimeout):
            await server.call("wait", {"seconds": 5})
        result = await server.call("wait", {"seconds": 0})
        assert not result.is_error
        await server.aclose()

    async def test_a_slow_start_is_given_up_on(self) -> None:
        async def never() -> Client:
            await asyncio.sleep(10)
            raise AssertionError("unreachable")

        class _SlowOpener(AbstractAsyncContextManager[Client]):
            async def __aenter__(self) -> Client:
                return await never()

            async def __aexit__(self, *exc_info: Any) -> bool:
                return False

        server = ManagedServer("slow", _SlowOpener, startup_timeout_s=0.05, retry_after_s=0.0)
        with pytest.raises(ServerUnavailable, match="did not start"):
            await server.tools()
        await server.aclose()


class TestFailure:
    async def test_a_connection_that_refuses(self) -> None:
        server = ManagedServer(
            "broken", lambda: _RefusingOpener(FileNotFoundError("no such file: npx"))
        )
        with pytest.raises(ServerUnavailable, match="npx"):
            await server.tools()
        assert server.failure is not None
        assert not server.connected

    async def test_it_is_not_retried_during_the_cooldown(self) -> None:
        attempts = 0

        def opener() -> AbstractAsyncContextManager[Client]:
            nonlocal attempts
            attempts += 1
            return _RefusingOpener(RuntimeError("boom"))

        server = ManagedServer("broken", opener, retry_after_s=60.0)
        for _ in range(3):
            with pytest.raises(ServerUnavailable):
                await server.tools()
        assert attempts == 1

    async def test_it_is_retried_once_the_cooldown_expires(self) -> None:
        attempts = 0

        def opener() -> AbstractAsyncContextManager[Client]:
            nonlocal attempts
            attempts += 1
            return _RefusingOpener(RuntimeError("boom"))

        server = ManagedServer("broken", opener, retry_after_s=0.0)
        for _ in range(2):
            with pytest.raises(ServerUnavailable):
                await server.tools()
        assert attempts == 2


class TestSettle:
    """Winding a worker down without swallowing the wrong cancellation."""

    async def test_a_worker_that_failed_is_not_re_raised(self) -> None:
        async def boom() -> None:
            raise RuntimeError("already recorded")

        await _settle(asyncio.create_task(boom()))

    async def test_the_workers_own_cancellation_is_absorbed(self) -> None:
        async def forever() -> None:
            await asyncio.sleep(10)

        worker = asyncio.create_task(forever())
        worker.cancel()
        await _settle(worker)

    async def test_our_own_cancellation_keeps_travelling(self) -> None:
        """Suppressing this is how a shutdown quietly stops being a shutdown."""

        async def forever() -> None:
            await asyncio.sleep(10)

        worker = asyncio.create_task(forever())
        waiting = asyncio.create_task(_settle(worker))
        await asyncio.sleep(0)
        waiting.cancel()

        with pytest.raises(asyncio.CancelledError):
            await waiting

        worker.cancel()


class TestDescribe:
    def test_a_task_group_is_unwrapped_to_its_leaf(self) -> None:
        """ "unhandled errors in a TaskGroup" tells a person nothing about their config."""
        group = ExceptionGroup("unhandled errors in a TaskGroup", [FileNotFoundError("npx")])
        assert _describe(group) == "FileNotFoundError: npx"

    def test_repeated_leaves_are_said_once(self) -> None:
        group = ExceptionGroup("boom", [RuntimeError("x"), RuntimeError("x")])
        assert _describe(group) == "RuntimeError: x"

    def test_an_exception_without_a_message_still_has_a_name(self) -> None:
        assert _describe(RuntimeError()) == "RuntimeError"


class TestStdio:
    async def test_a_real_subprocess(self, stdio_server: ManagedServer) -> None:
        tools = await stdio_server.tools()
        assert {tool.name for tool in tools} == {"spike__echo", "spike__die"}

        result = await stdio_server.call("echo", {"text": "hi"})
        assert not result.is_error

    async def test_a_server_that_dies_mid_conversation(self, stdio_server: ManagedServer) -> None:
        """The one the SDK does not do for us.

        A stdio server that exits leaves the client object looking perfectly healthy: every
        later call fails with "Connection closed" and nothing ever reconnects. The failure has
        to be noticed here, or one crashed subprocess is a dead tool until Hera restarts.
        """
        await stdio_server.tools()

        with pytest.raises(MCPError, match="Connection closed"):
            await stdio_server.call("die")

        assert not stdio_server.connected
        assert stdio_server.failure == "Connection closed"

    async def test_it_comes_back_after_the_server_died(self, stdio_server: ManagedServer) -> None:
        """Once the cooldown allows it, the next call starts a fresh process."""
        with pytest.raises(MCPError):
            await stdio_server.call("die")

        result = await stdio_server.call("echo", {"text": "still here"})

        assert not result.is_error
        assert stdio_server.connected

    async def test_a_command_that_does_not_exist(self, settings: ToolsSettings) -> None:
        server = ManagedServer.from_config(
            "ghost", StdioServer(command="definitely-not-a-real-command-xyz"), settings
        )
        with pytest.raises(ServerUnavailable):
            await server.tools()
        await server.aclose()

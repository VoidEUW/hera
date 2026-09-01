"""One MCP server's whole life: connect it lazily, keep it, and survive it dying.

Everything here exists because of one constraint that is easy to miss. The SDK's ``Client``
owns a task group -- a subprocess for stdio, a request loop in-process -- and anyio task groups
are *task-affine*: whoever enters the context has to be the one that leaves it. A client opened
during a web request and closed during application shutdown is opened and closed in two
different tasks, and unwinds into "cancel scope in a different task" rather than into a clean
exit.

So each server gets a **worker task** that owns its client for the whole time it is connected.
Callers hand work to a queue and wait on a future; the worker starts each call as a child task
of its own, so parallel tool calls to one server stay parallel -- which matters, because the
target model emits calls in batches and a turn is routinely three or four at once.

The failure behaviour is the other half. ADR 4: an unreachable server degrades to a missing
tool and never takes a turn down. Here that means a failed connection is recorded rather than
retried in a loop, its tools disappear from the catalogue, and the whole thing is tried again
once the cooldown has passed. Callers see :class:`~hera_tools.errors.ServerUnavailable`;
:class:`~hera_tools.registry.ToolRegistry` turns that into a tool result.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, TypeVar, cast

import httpx2
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.server.mcpserver import MCPServer
from mcp.shared.exceptions import MCPError
from mcp.types import CONNECTION_CLOSED, CallToolResult

from hera_tools.catalogue import Tool
from hera_tools.config import HttpServer, ServerConfig, StdioServer
from hera_tools.errors import ServerUnavailable, ToolTimeout
from hera_tools.naming import validate_server_name
from hera_tools.settings import ToolsSettings

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

ClientOpener = Callable[[], AbstractAsyncContextManager[Client]]
"""How to obtain a connected client. Called again on every reconnection attempt, so an opener
must be reusable -- an already-entered context manager is not."""


@dataclass
class _Job:
    """One unit of work for the worker task, and where its answer goes."""

    run: Callable[[Client], Awaitable[Any]]
    future: asyncio.Future[Any]
    task: asyncio.Task[None] | None = field(default=None, repr=False)
    abandoned: bool = False

    def abandon(self) -> None:
        """The caller gave up. Stop the work if it started; skip it if it has not."""
        self.abandoned = True
        if self.task is not None:
            self.task.cancel()


class ManagedServer:
    """A connection to one MCP server, opened on first use and kept until closed."""

    def __init__(
        self,
        name: str,
        opener: ClientOpener,
        *,
        call_timeout_s: float = 60.0,
        startup_timeout_s: float = 30.0,
        retry_after_s: float = 30.0,
    ) -> None:
        self.name = validate_server_name(name)
        self._opener = opener
        self._call_timeout_s = call_timeout_s
        self._startup_timeout_s = startup_timeout_s
        self._retry_after_s = retry_after_s

        self._jobs: asyncio.Queue[_Job | None] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._closed = False
        self._degraded = False
        self._failure: str | None = None
        self._failed_at = 0.0
        self._tools: tuple[Tool, ...] | None = None

    # -- construction ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls, name: str, config: ServerConfig, settings: ToolsSettings | None = None
    ) -> ManagedServer:
        """Build from one ``mcp.json`` entry."""
        settings = settings or ToolsSettings()
        return cls(
            name,
            _opener_for(config, settings),
            call_timeout_s=config.timeout_s or settings.call_timeout_s,
            startup_timeout_s=config.startup_timeout_s or settings.startup_timeout_s,
            retry_after_s=settings.retry_after_s,
        )

    @classmethod
    def in_process(
        cls, name: str, server: MCPServer, settings: ToolsSettings | None = None
    ) -> ManagedServer:
        """Build around a server object running inside this process.

        Hera's own tools take this path, and it is the same path as every other server: real
        MCP messages over an in-memory transport, a real catalogue, real permission checks.
        ADR 4 wanted them to be a server rather than a special case, and this is where that is
        either true or not.
        """
        settings = settings or ToolsSettings()
        return cls(
            name,
            lambda: Client(server=server),
            call_timeout_s=settings.call_timeout_s,
            startup_timeout_s=settings.startup_timeout_s,
            retry_after_s=settings.retry_after_s,
        )

    # -- state -------------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """Whether a call sent right now would reach the server.

        False for a worker whose transport has died under it -- see :meth:`_connection_lost`.
        """
        return self._worker is not None and not self._worker.done() and not self._degraded

    @property
    def failure(self) -> str | None:
        """Why the last attempt failed, for showing next to a server that has no tools."""
        return self._failure

    # -- use ---------------------------------------------------------------------------

    async def tools(self, *, refresh: bool = False) -> tuple[Tool, ...]:
        """The server's catalogue, namespaced, cached after the first successful listing.

        Cached because it is asked for on every turn and answered by a round-trip over a pipe.
        A server that adds tools while running sends ``notifications/tools/list_changed``;
        acting on that is worth doing once anything actually does it -- until then, ``refresh``
        is the manual answer.
        """
        if self._tools is not None and not refresh:
            return self._tools

        listing = await self._submit(
            lambda client: client.list_tools(),
            timeout_s=self._call_timeout_s,
            label=f"{self.name}: list_tools",
        )
        self._tools = tuple(Tool.from_mcp(self.name, tool) for tool in listing.tools)
        return self._tools

    async def call(
        self,
        tool: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
        context: Mapping[str, str] | None = None,
    ) -> CallToolResult:
        """Call one tool by its **local** name and return the protocol result.

        A tool that fails on purpose comes back with ``is_error`` set, not as an exception --
        that is the protocol's own distinction and it is worth preserving this far up.

        ``context`` rides in the request's ``_meta`` rather than in ``arguments``, and this
        package never looks inside it (ADR 12). Two reasons it is not an argument: the model
        chooses arguments, so anything the caller must decide would be forgeable; and a field in
        the schema is a field the model can see and will try to fill in. Anything sent here has
        to be a string the *application* put there.
        """
        budget = timeout_s or self._call_timeout_s
        meta = dict(context) if context else None
        return await self._submit(
            # `meta` is a TypedDict at runtime, which is to say a dict. Passing one with keys the
            # SDK does not declare is how a namespaced extension is meant to travel.
            lambda client: client.call_tool(tool, arguments or {}, meta=cast(Any, meta)),
            timeout_s=budget,
            label=f"{self.name}: {tool}",
        )

    async def aclose(self) -> None:
        """Stop the worker and let it close its own client, in its own task."""
        self._closed = True
        await self._retire()

    # -- internals ---------------------------------------------------------------------

    async def _submit(
        self, run: Callable[[Client], Awaitable[_T]], *, timeout_s: float, label: str
    ) -> _T:
        """Hand one piece of work to the worker and wait for its answer.

        ``timeout_s`` covers the work, not the connecting: a cold ``npx`` server takes seconds
        to start, and charging that to the first call would make every first call fail. Starting
        has its own budget, in :meth:`_ensure_running`.
        """
        await self._ensure_running()

        job = _Job(run=run, future=asyncio.get_running_loop().create_future())
        self._jobs.put_nowait(job)
        try:
            async with asyncio.timeout(timeout_s):
                return cast(_T, await job.future)
        except TimeoutError as exc:
            job.abandon()
            raise ToolTimeout(label, timeout_s) from exc

    async def _ensure_running(self) -> None:
        """Connect if we are not connected, unless we recently failed to.

        Under a lock, so that three parallel tool calls on a cold server produce one
        subprocess and not three.
        """
        if self._closed:
            raise ServerUnavailable(self.name, "the client has been closed")

        async with self._lock:
            if self.connected:
                return

            await self._retire()
            if self._failure is not None and not self._cooldown_expired():
                raise ServerUnavailable(self.name, self._failure)

            ready: asyncio.Future[None] = asyncio.get_running_loop().create_future()
            self._worker = asyncio.create_task(self._serve(ready), name=f"mcp:{self.name}")
            try:
                async with asyncio.timeout(self._startup_timeout_s):
                    await ready
            except TimeoutError as exc:
                self._record_failure(f"did not start within {self._startup_timeout_s:g}s")
                await self._cancel_worker()
                raise ServerUnavailable(self.name, str(self._failure)) from exc
            except ServerUnavailable:
                self._worker = None
                raise

            self._failure = None

    def _cooldown_expired(self) -> bool:
        return time.monotonic() - self._failed_at >= self._retry_after_s

    async def _retire(self) -> None:
        """Wind down whatever worker there is, so a new one can take its place.

        Asks rather than cancels: the worker closing its own client is the entire reason it
        exists, and a cancelled task unwinds an anyio scope from the wrong side.
        """
        worker, self._worker = self._worker, None
        self._degraded = False
        if worker is None:
            return
        if not worker.done():
            self._jobs.put_nowait(None)
        await _settle(worker)

    async def _cancel_worker(self) -> None:
        """The blunt version, for a worker that never finished connecting and cannot be asked."""
        worker, self._worker = self._worker, None
        self._degraded = False
        if worker is None:  # pragma: no cover -- only called with one running
            return
        worker.cancel()
        await _settle(worker)

    def _connection_lost(self, reason: str) -> None:
        """The transport is gone even though the client object still looks alive.

        A stdio server that exits does not close the client -- every subsequent call simply
        fails with "Connection closed", forever, because from the outside the worker is still
        running happily. So the state is marked here, synchronously, before the failing call
        even returns to its caller: the next use finds a server that is not connected, retires
        this worker and starts a new one. Without it, one crashed subprocess is a dead tool
        until Hera restarts, which is precisely what ADR 4 says must not happen.
        """
        if self._degraded:
            return
        self._degraded = True
        self._record_failure(reason)
        self._jobs.put_nowait(None)

    def _record_failure(self, reason: str) -> None:
        self._failure = reason
        self._failed_at = time.monotonic()
        self._tools = None
        logger.warning("MCP server %s unavailable: %s", self.name, reason)

    async def _serve(self, ready: asyncio.Future[None]) -> None:
        """Own one client for as long as it lives, and run everything that arrives for it."""
        running: set[asyncio.Task[None]] = set()
        try:
            async with self._opener() as client:
                if not ready.done():
                    ready.set_result(None)
                while True:
                    job = await self._jobs.get()
                    if job is None:
                        break
                    if job.abandoned:
                        continue
                    task = asyncio.create_task(self._execute(client, job))
                    job.task = task
                    running.add(task)
                    task.add_done_callback(running.discard)
                if running:
                    await asyncio.gather(*running, return_exceptions=True)
        except Exception as exc:
            reason = _describe(exc)
            self._record_failure(reason)
            failure = ServerUnavailable(self.name, reason)
            if not ready.done():
                ready.set_exception(failure)
        finally:
            # Also reached when the worker is cancelled outright, which is how a crashed
            # transport usually arrives: whoever is queued behind it should hear that now
            # rather than wait out their own timeout.
            self._fail_pending(
                ServerUnavailable(self.name, self._failure or "the connection closed")
            )

    async def _execute(self, client: Client, job: _Job) -> None:
        try:
            result = await job.run(client)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not job.future.done():
                job.future.set_exception(exc)
            if isinstance(exc, MCPError) and exc.code == CONNECTION_CLOSED:
                self._connection_lost(exc.message)
        else:
            if not job.future.done():
                job.future.set_result(result)

    def _fail_pending(self, failure: ServerUnavailable) -> None:
        """Nobody is going to answer these now; say so rather than let them time out."""
        while not self._jobs.empty():
            job = self._jobs.get_nowait()
            if job is not None and not job.future.done():
                job.future.set_exception(failure)


async def _settle(worker: asyncio.Task[None]) -> None:
    """Wait for a worker to finish, keeping its failures to itself.

    A ``CancelledError`` is only swallowed when it is the worker's own. If it arrives because
    *we* were cancelled while waiting, it has to keep travelling -- suppressing that is how a
    shutdown quietly stops being a shutdown.

    Told apart by asking whether *this* task has a cancellation pending, not by asking whether
    the worker was cancelled: being cancelled while awaiting a task cancels that task too, so
    ``worker.cancelled()`` is true either way and answers the wrong question.
    """
    try:
        await worker
    except asyncio.CancelledError:
        current = asyncio.current_task()
        if current is not None and current.cancelling():
            raise
    except Exception:
        logger.debug("MCP worker %s ended with an error", worker.get_name(), exc_info=True)


def _describe(exc: BaseException) -> str:
    """A one-line reason, unwrapping the task groups the SDK's transports raise through.

    A failed stdio launch arrives as an ``ExceptionGroup`` whose message is "unhandled errors
    in a TaskGroup", which tells a person nothing. The leaf is the part worth showing.
    """
    if isinstance(exc, BaseExceptionGroup):
        leaves = [_describe(inner) for inner in exc.exceptions]
        return "; ".join(dict.fromkeys(leaves)) or str(exc)
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def _opener_for(config: ServerConfig, settings: ToolsSettings) -> ClientOpener:
    read_timeout = config.timeout_s or settings.call_timeout_s
    if isinstance(config, StdioServer):
        parameters = StdioServerParameters(
            command=config.command,
            args=list(config.args),
            env=dict(config.env) or None,
            cwd=config.cwd,
        )
        return lambda: Client(server=parameters, read_timeout_seconds=read_timeout)
    return _http_opener(config, read_timeout)


def _http_opener(config: HttpServer, read_timeout: float) -> ClientOpener:
    """Streamable HTTP, with the headers a remote server needs to authenticate us.

    The SDK takes headers by way of an HTTP client rather than as an argument, so one is built
    here and closed with the connection. ``httpx2`` is the SDK's own client library, not the
    ``httpx`` that ``hera_providers`` uses -- the two are separate packages and mixing them up
    produces a type error rather than a runtime surprise.
    """

    @asynccontextmanager
    async def opener() -> AsyncIterator[Client]:
        async with httpx2.AsyncClient(headers=dict(config.headers)) as http_client:
            transport = streamable_http_client(config.url, http_client=http_client)
            async with Client(server=transport, read_timeout_seconds=read_timeout) as client:
                yield client

    return opener

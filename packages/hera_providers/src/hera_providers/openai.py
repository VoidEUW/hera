"""Talking to an OpenAI-compatible endpoint over httpx.

This module is deliberately thin. It moves bytes, maps HTTP failures onto
:mod:`hera_providers.errors`, and hands every decoded chunk to a
:class:`~hera_providers.base.StreamAdapter`. Everything that is *about a model* -- reasoning
channels, tool-call assembly, finish reasons -- lives in the adapter, so a second model family
costs an adapter and not a second transport.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from hera_providers.base import StreamAdapter
from hera_providers.errors import (
    MalformedResponse,
    ProviderError,
    ProviderHTTPError,
    ProviderTimeout,
    ProviderUnavailable,
    StreamInterrupted,
)
from hera_providers.events import Event
from hera_providers.qwen import QwenAdapter
from hera_providers.request import ChatMessage, ChatRequest, Role
from hera_providers.settings import ProviderSettings

DONE_SENTINEL = "[DONE]"
MAX_ERROR_BODY_CHARS = 2000
"""Error bodies are truncated: a local server can answer a bad request with a stack trace, and
an exception message nobody can read is not more useful than a short one."""


class OpenAICompatibleProvider:
    """Streams turns and computes embeddings against one endpoint.

    Pass an ``httpx.AsyncClient`` to test against ``httpx.MockTransport``, or to share a
    connection pool. A client passed in is not closed by :meth:`aclose` -- whoever opened it
    owns it.
    """

    def __init__(
        self,
        settings: ProviderSettings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        adapter_factory: type[StreamAdapter] = QwenAdapter,
    ) -> None:
        self._settings = settings if settings is not None else ProviderSettings()
        self._adapter_factory = adapter_factory
        self._owns_client = client is None
        self._client = client if client is not None else build_client(self._settings)

    @property
    def settings(self) -> ProviderSettings:
        return self._settings

    @property
    def client(self) -> httpx.AsyncClient:
        """The underlying client, for sharing a connection pool or inspecting configuration."""
        return self._client

    async def __aenter__(self) -> OpenAICompatibleProvider:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def stream(self, request: ChatRequest) -> AsyncIterator[Event]:
        """Stream one turn as events, ending in exactly one ``TurnEnd``."""
        adapter = self._adapter_factory()
        payload = chat_payload(request, stream=True)
        try:
            async with self._client.stream("POST", "/chat/completions", json=payload) as response:
                await _raise_for_status(response)
                async for line in response.aiter_lines():
                    data = _frame_payload(line)
                    if data is None:
                        continue
                    chunk = _decode_object(data, source="the stream")
                    for event in adapter.feed(chunk):
                        yield event
        except httpx.HTTPError as exc:
            raise _transport_error(exc, self._settings.base_url) from exc

        for event in adapter.finish():
            yield event

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        """Return one vector per input, in input order."""
        if not texts:
            return []
        name = model or self._settings.embedding_model
        if not name:
            raise ProviderError(
                "no embedding model configured; set HERA_PROVIDER_EMBEDDING_MODEL or pass model="
            )
        payload = await self._post("/embeddings", {"model": name, "input": list(texts)})
        rows = payload.get("data")
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise MalformedResponse(f"expected {len(texts)} embeddings, got {payload!r}")
        # The protocol does not promise input order, only an `index` on every row.
        ordered = sorted(rows, key=lambda row: int(row.get("index", 0)))
        return [[float(value) for value in row["embedding"]] for row in ordered]

    async def models(self) -> list[str]:
        """Model ids the endpoint offers. Useful for a "test connection" button."""
        payload = await self._request("GET", "/models", None)
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise MalformedResponse(f"/models did not return a data list: {payload!r}")
        return sorted(str(row["id"]) for row in rows if "id" in row)

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, body)

    async def _request(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, json=body)
        except httpx.HTTPError as exc:
            raise _transport_error(exc, self._settings.base_url) from exc
        await _raise_for_status(response)
        return _decode_object(response.text, source=path)


def chat_payload(request: ChatRequest, *, stream: bool) -> dict[str, Any]:
    """Map a :class:`ChatRequest` onto the wire body.

    Optional fields are omitted rather than sent as ``null``: local servers vary in how well
    they tolerate an explicit null where they expected a number.
    """
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": [_message_payload(message) for message in request.messages],
        "stream": stream,
    }
    if stream:
        # Without this most servers send no usage at all on a streamed response.
        payload["stream_options"] = {"include_usage": True}
    if request.tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in request.tools
        ]
        payload["tool_choice"] = request.tool_choice
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.top_p is not None:
        payload["top_p"] = request.top_p
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.stop:
        payload["stop"] = request.stop
    payload.update(request.extra)
    return payload


def _message_payload(message: ChatMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role.value, "content": message.content}
    if message.role is Role.TOOL and message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in message.tool_calls
        ]
    return payload


def _frame_payload(line: str) -> str | None:
    """The JSON of one SSE frame, or ``None`` for anything that carries no chunk."""
    stripped = line.strip()
    if not stripped or stripped.startswith(":") or not stripped.startswith("data:"):
        return None
    data = stripped[len("data:") :].strip()
    return None if data == DONE_SENTINEL else data


def _transport_error(exc: httpx.HTTPError, base_url: str) -> ProviderError:
    """Map an httpx failure onto this package's vocabulary.

    Everything above catches ``ProviderError``, so nothing from httpx may escape -- a raw
    ``RemoteProtocolError`` reaching the turn loop is an unhandled crash where a persisted
    partial answer belongs. Ordered by specificity: ``ConnectTimeout`` is a ``TimeoutException``
    and not a ``ConnectError``, so the timeout branch has to come first.
    """
    if isinstance(exc, httpx.TimeoutException):
        return ProviderTimeout(f"{base_url} did not answer in time")
    if isinstance(exc, httpx.ConnectError | httpx.ProxyError | httpx.UnsupportedProtocol):
        return ProviderUnavailable(f"cannot reach {base_url}: {exc}")
    # Everything left reached the server and failed afterwards: a dropped connection, a
    # truncated body, a read that died part-way. Whatever already arrived is real.
    return StreamInterrupted(f"the connection to {base_url} broke: {exc}")


def _decode(data: str) -> object:
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise MalformedResponse(f"could not decode {data[:200]!r}") from exc


def _decode_object(data: str, *, source: str) -> dict[str, Any]:
    decoded = _decode(data)
    if not isinstance(decoded, dict):
        raise MalformedResponse(f"{source} did not return a JSON object: {decoded!r}")
    return decoded


async def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    # A streamed response has no body yet at this point; read it before reporting.
    body = (await response.aread()).decode("utf-8", errors="replace")
    raise ProviderHTTPError(response.status_code, body[:MAX_ERROR_BODY_CHARS])


def build_client(settings: ProviderSettings) -> httpx.AsyncClient:
    """The client :class:`OpenAICompatibleProvider` uses when it is not given one.

    Public so that an application wanting one shared pool across several providers can build
    it here rather than reconstructing the header and timeout choices by hand.
    """
    headers = {"Accept": "application/json"}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"
    return httpx.AsyncClient(
        base_url=settings.base_url.rstrip("/"),
        headers=headers,
        timeout=httpx.Timeout(settings.timeout_s, connect=settings.connect_timeout_s),
    )

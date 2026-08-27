"""The transport: request shape, stream framing, and how failures are named.

Driven through ``httpx.MockTransport``, so these are real requests through the real client
without a server. Anything needing an actual endpoint is marked ``live`` and stays out of CI.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from hera_providers import (
    ChatMessage,
    ChatRequest,
    EmbeddingProvider,
    ImagePart,
    MalformedResponse,
    OpenAICompatibleProvider,
    Provider,
    ProviderError,
    ProviderHTTPError,
    ProviderSettings,
    ProviderTimeout,
    ProviderUnavailable,
    Role,
    StreamInterrupted,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallReady,
    ToolSpec,
    TurnEnd,
    build_client,
    chat_payload,
)

Handler = Callable[[httpx.Request], httpx.Response]
BASE_URL = "http://model.test/v1"


def make_provider(handler: Handler, **overrides: Any) -> OpenAICompatibleProvider:
    settings = ProviderSettings(base_url=BASE_URL, model="qwen-test", **overrides)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=BASE_URL)
    return OpenAICompatibleProvider(settings, client=client)


def sse(*frames: dict[str, Any], done: bool = True) -> str:
    body = "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames)
    return body + "data: [DONE]\n\n" if done else body


def turn(*, content: str | None = None, finish: str | None = None) -> dict[str, Any]:
    delta = {} if content is None else {"content": content}
    return {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}


def request(**overrides: Any) -> ChatRequest:
    defaults: dict[str, Any] = {
        "model": "qwen-test",
        "messages": [ChatMessage(role=Role.USER, content="hi")],
    }
    return ChatRequest(**{**defaults, **overrides})


async def collect(provider: OpenAICompatibleProvider, req: ChatRequest) -> list[Any]:
    return [event async for event in provider.stream(req)]


# -- the protocols ----------------------------------------------------------------------


def test_the_provider_satisfies_both_protocols() -> None:
    """Checked by the type checker, not by this assertion -- the annotations are the test."""
    provider = make_provider(lambda _r: httpx.Response(200, json={}))
    streaming: Provider = provider
    embedding: EmbeddingProvider = provider

    assert callable(streaming.stream)
    assert callable(embedding.embed)


# -- streaming --------------------------------------------------------------------------


async def test_a_stream_becomes_events() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text=sse(turn(content="Hel"), turn(content="lo"), turn(finish="stop"))
        )

    events = await collect(make_provider(handler), request())

    assert [e for e in events if isinstance(e, TextDelta)] == [
        TextDelta(text="Hel"),
        TextDelta(text="lo"),
    ]
    assert events[-1] == TurnEnd(reason="stop")


async def test_frames_that_carry_no_chunk_are_skipped() -> None:
    """Blank separators, comment keep-alives and the terminator are all normal traffic."""

    def handler(_request: httpx.Request) -> httpx.Response:
        body = ": keep-alive\n\n" + sse(turn(content="x"), turn(finish="stop"))
        return httpx.Response(200, text=body)

    events = await collect(make_provider(handler), request())

    assert [e for e in events if isinstance(e, TextDelta)] == [TextDelta(text="x")]


async def test_a_frame_that_is_not_json_is_a_malformed_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="data: {not json}\n\n")

    with pytest.raises(MalformedResponse):
        await collect(make_provider(handler), request())


async def test_a_frame_that_is_json_but_not_an_object_is_a_malformed_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="data: [1, 2]\n\n")

    with pytest.raises(MalformedResponse):
        await collect(make_provider(handler), request())


# -- the request body -------------------------------------------------------------------


async def test_the_request_asks_for_usage_with_the_stream() -> None:
    """Without `stream_options` most servers report no token counts on a streamed answer."""
    sent: list[dict[str, Any]] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(http_request.content))
        return httpx.Response(200, text=sse(turn(finish="stop")))

    await collect(make_provider(handler), request())

    assert sent[0]["stream"] is True
    assert sent[0]["stream_options"] == {"include_usage": True}


def test_optional_fields_are_omitted_rather_than_sent_as_null() -> None:
    """Local servers vary in how well they tolerate an explicit null where a number belongs."""
    payload = chat_payload(request(), stream=False)

    assert "temperature" not in payload
    assert "max_tokens" not in payload
    assert "tools" not in payload
    assert "stream_options" not in payload


def test_set_fields_are_sent() -> None:
    payload = chat_payload(
        request(temperature=0.2, top_p=0.9, max_tokens=64, stop=["\n\n"]), stream=False
    )

    assert payload["temperature"] == 0.2
    assert payload["top_p"] == 0.9
    assert payload["max_tokens"] == 64
    assert payload["stop"] == ["\n\n"]


def test_tools_are_sent_in_the_function_envelope_with_a_choice() -> None:
    spec = ToolSpec(
        name="hera__emotion",
        description="Show a stance.",
        parameters={"type": "object", "properties": {"kind": {"type": "string"}}},
    )
    payload = chat_payload(request(tools=[spec]), stream=False)

    assert payload["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "hera__emotion",
                "description": "Show a stance.",
                "parameters": spec.parameters,
            },
        }
    ]
    assert payload["tool_choice"] == "auto"


def test_a_tool_result_names_the_call_it_answers() -> None:
    """A model that cannot match a result to its call ignores the result."""
    payload = chat_payload(
        request(
            messages=[
                ChatMessage(
                    role=Role.ASSISTANT,
                    tool_calls=[ToolCall(id="c1", name="hera__note", arguments={"text": "hi"})],
                ),
                ChatMessage(role=Role.TOOL, content="ok", tool_call_id="c1"),
            ]
        ),
        stream=False,
    )

    assistant, tool = payload["messages"]
    assert assistant["tool_calls"][0]["id"] == "c1"
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"text": "hi"}
    assert tool["tool_call_id"] == "c1"


def test_prose_stays_a_bare_string_on_the_wire() -> None:
    """Wrapping every message in a one-element list is equally valid by the specification and
    is not what local servers have been tested against. Being unremarkable is worth more."""
    payload = chat_payload(
        request(messages=[ChatMessage(role=Role.USER, content="hello")]), stream=False
    )

    assert payload["messages"][0]["content"] == "hello"


def test_a_picture_is_sent_as_typed_blocks() -> None:
    payload = chat_payload(
        request(
            messages=[
                ChatMessage(
                    role=Role.USER,
                    content=[
                        TextPart(text="what is this?"),
                        ImagePart(url="data:image/png;base64,iVBOR"),
                    ],
                )
            ]
        ),
        stream=False,
    )

    assert payload["messages"][0]["content"] == [
        {"type": "text", "text": "what is this?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR"}},
    ]


def test_detail_is_omitted_unless_it_was_asked_for() -> None:
    """Same reason as every other optional field: a null where a server expected a word."""
    payload = chat_payload(
        request(messages=[ChatMessage(role=Role.USER, content=[ImagePart(url="http://x/a.png")])]),
        stream=False,
    )

    assert payload["messages"][0]["content"][0]["image_url"] == {"url": "http://x/a.png"}


def test_the_words_of_a_message_are_readable_whichever_shape_it_is() -> None:
    """Anything wanting a message for its words — a title, a budget, a log line — asks for
    `.text` and does not have to know a picture came with it."""
    parts = ChatMessage(
        role=Role.USER,
        content=[TextPart(text="look at "), ImagePart(url="data:image/png;base64,x")],
    )

    assert parts.text == "look at "
    assert ChatMessage(role=Role.USER, content="plain").text == "plain"


def test_extra_is_merged_last_so_a_server_specific_field_can_be_passed_through() -> None:
    payload = chat_payload(request(extra={"reasoning_effort": "high"}), stream=False)

    assert payload["reasoning_effort"] == "high"


# -- failures ---------------------------------------------------------------------------


async def test_an_error_status_carries_its_status_and_body() -> None:
    """A local server answers a bad request with something worth reading; keep it."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="model 'qwen-test' is not loaded")

    with pytest.raises(ProviderHTTPError) as caught:
        await collect(make_provider(handler), request())

    assert caught.value.status_code == 400
    assert "not loaded" in caught.value.body


async def test_nothing_listening_is_reported_as_unavailable() -> None:
    """The most common failure of a self-hosted setup deserves its own name."""

    def handler(http_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=http_request)

    with pytest.raises(ProviderUnavailable):
        await collect(make_provider(handler), request())


async def test_a_slow_endpoint_is_reported_as_a_timeout() -> None:
    """Distinct from unavailable: the remedy is a longer timeout, not a restart."""

    def handler(http_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=http_request)

    with pytest.raises(ProviderTimeout):
        await collect(make_provider(handler), request())


async def test_a_connection_dropped_mid_answer_keeps_what_arrived() -> None:
    """A local server killed part-way through generation -- out of memory, a model swap --
    must not reach the turn loop as a raw httpx error. Everything above catches ProviderError,
    so an unmapped one is an unhandled crash exactly where a persisted partial answer belongs.

    MockTransport cannot express this: it asserts the body is fully readable. Hence a
    transport that breaks the way a real one does.
    """

    class Dropping(httpx.AsyncBaseTransport):
        async def handle_async_request(self, http_request: httpx.Request) -> httpx.Response:
            async def body() -> AsyncIterator[bytes]:
                yield f"data: {json.dumps(turn(content='half an ans'))}\n\n".encode()
                raise httpx.RemoteProtocolError("peer closed connection", request=http_request)

            return httpx.Response(200, content=body())

    settings = ProviderSettings(base_url=BASE_URL)
    client = httpx.AsyncClient(transport=Dropping(), base_url=BASE_URL)
    provider = OpenAICompatibleProvider(settings, client=client)

    seen: list[Any] = []
    with pytest.raises(StreamInterrupted):
        async for event in provider.stream(request()):
            seen.append(event)

    assert seen == [TextDelta(text="half an ans")]


async def test_the_same_failures_are_named_the_same_way_off_the_stream() -> None:
    def unreachable(http_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=http_request)

    def slow(http_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow", request=http_request)

    with pytest.raises(ProviderUnavailable):
        await make_provider(unreachable).models()
    with pytest.raises(ProviderTimeout):
        await make_provider(slow).models()


# -- embeddings -------------------------------------------------------------------------


async def test_embeddings_come_back_in_input_order() -> None:
    """The protocol promises an `index` on every row, not an order."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ]
            },
        )

    vectors = await make_provider(handler, embedding_model="embed").embed(["first", "second"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


async def test_embedding_nothing_makes_no_request() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request to {http_request.url}")

    assert await make_provider(handler, embedding_model="embed").embed([]) == []


async def test_embedding_without_a_configured_model_says_so() -> None:
    """Embeddings being off is configuration, not a server failure."""
    provider = make_provider(lambda _r: httpx.Response(200, json={}))

    with pytest.raises(ProviderError, match="no embedding model"):
        await provider.embed(["text"])


async def test_a_short_embedding_response_is_malformed() -> None:
    """Silently returning fewer vectors than inputs would misalign every caller's zip()."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1]}]})

    with pytest.raises(MalformedResponse):
        await make_provider(handler, embedding_model="embed").embed(["a", "b"])


async def test_an_explicit_model_overrides_the_configured_one() -> None:
    sent: list[dict[str, Any]] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(http_request.content))
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})

    await make_provider(handler, embedding_model="configured").embed(["a"], model="explicit")

    assert sent[0]["model"] == "explicit"


# -- models -----------------------------------------------------------------------------


async def test_models_are_listed_sorted() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "qwen"}, {"id": "embed"}, {}]})

    assert await make_provider(handler).models() == ["embed", "qwen"]


async def test_a_models_response_without_a_data_list_is_malformed() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"object": "list"})

    with pytest.raises(MalformedResponse):
        await make_provider(handler).models()


# -- client ownership -------------------------------------------------------------------


def test_the_provider_exposes_the_settings_it_was_built_with() -> None:
    """Callers build a ChatRequest from `provider.settings.model` rather than repeating it."""
    assert make_provider(lambda _r: httpx.Response(200, json={})).settings.model == "qwen-test"


def test_a_configured_client_carries_the_key_only_when_there_is_one() -> None:
    """Most local servers need no authentication and reject a bearer header they did not ask
    for, so sending an empty one would break the default deployment."""
    assert "authorization" not in build_client(ProviderSettings()).headers
    assert build_client(ProviderSettings(api_key="k")).headers["authorization"] == "Bearer k"


@pytest.mark.parametrize("configured", ["http://model.test/v1", "http://model.test/v1/"])
def test_the_base_url_resolves_the_same_with_or_without_a_trailing_slash(configured: str) -> None:
    """Whether someone pastes the URL with a slash is not something they should have to think
    about, and `/v1//chat/completions` is a 404 on most servers."""
    client = build_client(ProviderSettings(base_url=configured))
    url = client.build_request("POST", "/chat/completions").url

    assert str(url) == "http://model.test/v1/chat/completions"


async def test_closing_releases_a_client_the_provider_opened() -> None:
    async with OpenAICompatibleProvider(ProviderSettings(base_url=BASE_URL)) as provider:
        client = provider.client

    assert client.is_closed


async def test_closing_leaves_an_injected_client_alone() -> None:
    """Whoever opened the pool owns it; closing it here would surprise the other users."""
    provider = make_provider(lambda _r: httpx.Response(200, json={}))
    await provider.aclose()

    assert not provider.client.is_closed


# -- end to end -------------------------------------------------------------------------


async def test_a_tool_calling_turn_arrives_as_complete_calls() -> None:
    """The whole path in one test: HTTP, framing, adapter, union."""

    def handler(_request: httpx.Request) -> httpx.Response:
        frames = [
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "c1",
                                    "function": {"name": "hera__emotion", "arguments": '{"kind"'},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [{"index": 0, "function": {"arguments": ':"joke"}'}}]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        ]
        return httpx.Response(200, text=sse(*frames))

    events = await collect(make_provider(handler), request())

    assert events[0] == ToolCallReady(
        id="c1",
        name="hera__emotion",
        arguments={"kind": "joke"},
        raw_arguments='{"kind":"joke"}',
    )
    assert events[1] == TurnEnd(reason="tool_calls")

"""What a local endpoint says about itself, and what to do when it says nothing.

A self-hosted server is under no obligation to publish anything, and the two that do disagree in
useful ways. ``llama.cpp`` serves ``/props`` with both a ``chat_template_caps`` object and the
Jinja ``chat_template`` itself; for MiniCPM5-2B the caps say
``"supports_reasoning_effort": false`` and the template mentions ``enable_thinking`` three times
and ``reasoning_effort`` not at all. Two independent signals from the same server, agreeing.

Everything uncertain here answers ``False``, because both flags mean *draw a control that would
work* and a control that does nothing is worse than an absent one.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from hera_providers.capabilities import (
    NOTHING,
    Capabilities,
    EndpointCapabilities,
    props_url,
    template_capabilities,
)

Handler = Callable[[httpx.Request], httpx.Response]

MINICPM_TEMPLATE = (
    "{%- if messages[0].role == 'system' %}"
    "{{- '<|im_start|>system\\n' + messages[0].content + '<|im_end|>\\n' }}"
    "{%- endif %}"
    "{%- if add_generation_prompt %}"
    "{%- if enable_thinking is defined %}"
    "{%- if enable_thinking is false %}"
    "{{- '<think>\\n\\n</think>\\n\\n' }}"
    "{%- elif enable_thinking is true %}"
    "{{- '<think>\\n' }}"
    "{%- endif %}"
    "{%- endif %}"
)

QWEN_TEMPLATE = (
    "{%- if enable_thinking is undefined or enable_thinking is true %}"
    "{%- set resolved_reasoning_effort = reasoning_effort|default('xhigh') %}"
    "{%- if resolved_reasoning_effort not in ('xhigh', 'medium', 'low') %}"
    "{{- raise_exception('Unexpected reasoning effort') }}"
    "{%- endif %}"
)


def props(**extra: object) -> dict[str, object]:
    """A `/props` body. Flat, because that is what llama.cpp serves -- the template and the
    capability object are top-level keys, not entries under a `data` envelope."""
    return dict(extra)


@pytest.fixture(autouse=True)
def _no_shared_cache() -> None:
    EndpointCapabilities.forget()


def _client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestPropsUrl:
    def test_the_openai_compatible_suffix_is_dropped(self) -> None:
        # `/props` hangs off the server's root, and a base_url of `.../v1` is a routes prefix
        # rather than a prefix of the server.
        assert props_url("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080"
        assert props_url("http://host/api/v1") == "http://host/api"
        assert props_url("http://host/openai/v1/") == "http://host/openai"

    def test_a_bare_root_is_left_alone(self) -> None:
        assert props_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"

    def test_an_unrecognised_path_is_not_guessed_at(self) -> None:
        # A server on a path prefix is unusual, and rearranging its base_url to find `/props`
        # would be the kind of guessing this whole arrangement exists to avoid.
        assert props_url("https://gw.example/team-a/llm/v1beta") == (
            "https://gw.example/team-a/llm/v1beta"
        )


class TestTemplateCapabilities:
    def test_a_declared_capability_is_taken_at_face_value(self) -> None:
        # MiniCPM5, verbatim: the server says the field is not honoured, and the template agrees.
        found = template_capabilities(
            props(
                chat_template=MINICPM_TEMPLATE,
                chat_template_caps={"supports_reasoning_effort": False, "supports_tools": True},
            )
        )

        assert found == Capabilities(supports_reasoning_effort=False, thinking_toggle=True)

    def test_a_capability_the_server_omits_falls_back_to_the_template(self) -> None:
        # No caps object at all. A template that *reads* reasoning_effort is one that honours it.
        found = template_capabilities(props(chat_template=QWEN_TEMPLATE))

        assert found.supports_reasoning_effort is True
        assert found.thinking_toggle is True

    def test_a_template_with_neither_means_neither_control(self) -> None:
        found = template_capabilities(props(chat_template="{{ messages[0].content }}"))

        assert found == NOTHING

    def test_a_whole_word_is_required(self) -> None:
        # `supports_reasoning_effort` in a comment is not a declaration, and a longer name
        # containing the field is a different name.
        template = "{# supports_reasoning_effort is not read #} {{ my_reasoning_effort_setting }}"
        assert template_capabilities(props(chat_template=template)) == NOTHING

    def test_an_empty_template_is_not_a_template(self) -> None:
        assert template_capabilities(props(chat_template="")) == NOTHING
        assert template_capabilities(props(chat_template=None)) == NOTHING

    def test_rubbish_is_nothing_rather_than_an_exception(self) -> None:
        rubbish: list[object] = [{}, {"data": "nonsense"}, [], "nonsense", None, 7]
        for payload in rubbish:
            assert template_capabilities(payload) == NOTHING

    def test_a_caps_flag_of_the_wrong_type_is_ignored(self) -> None:
        found = template_capabilities(
            props(
                chat_template=QWEN_TEMPLATE,
                chat_template_caps={"supports_reasoning_effort": "yes"},
            )
        )

        assert found.supports_reasoning_effort is True, "falls through to the template"


class TestLoading:
    async def test_an_endpoint_that_answers_is_asked_once(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                200,
                json=props(chat_template=MINICPM_TEMPLATE, chat_template_caps={}),
            )

        async with _client(handler) as client:
            first = await EndpointCapabilities.load("http://h:1/v1", client=client)
            second = await EndpointCapabilities.load("http://h:1/v1", client=client)

        assert first.thinking_toggle is True
        assert second == first
        assert calls == 1

    async def test_it_asks_at_the_root_not_under_the_api_prefix(self) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.path)
            return httpx.Response(200, json=props(chat_template=MINICPM_TEMPLATE))

        async with _client(handler) as client:
            await EndpointCapabilities.load("http://h:1/v1", client=client)

        assert seen == ["/props"]

    async def test_a_404_is_an_answer_and_is_cached(self) -> None:
        # vLLM, LM Studio, a proxy: no `/props`. That is a whole answer, not a failure to retry.
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(404)

        async with _client(handler) as client:
            assert await EndpointCapabilities.load("http://h:1/v1", client=client) == NOTHING
            assert await EndpointCapabilities.load("http://h:1/v1", client=client) == NOTHING

        assert calls == 1

    async def test_an_unreachable_endpoint_is_nothing_and_is_cached(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ConnectError("refused")

        async with _client(handler) as client:
            assert (
                await EndpointCapabilities.load("http://127.0.0.1:9/v1", client=client) == NOTHING
            )
            assert (
                await EndpointCapabilities.load("http://127.0.0.1:9/v1", client=client) == NOTHING
            )

        assert calls == 1

    async def test_a_body_that_is_not_json_is_nothing(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>hello</html>")

        async with _client(handler) as client:
            assert await EndpointCapabilities.load("http://h:1/v1", client=client) == NOTHING

    async def test_two_endpoints_are_answered_separately(self) -> None:
        # The cache is per base_url: a llama.cpp on loopback and a vLLM on the LAN are different
        # servers and one of them answering says nothing about the other.
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "local":
                return httpx.Response(200, json=props(chat_template=MINICPM_TEMPLATE))
            return httpx.Response(404)

        async with _client(handler) as client:
            local = await EndpointCapabilities.load("http://local:8080/v1", client=client)
            remote = await EndpointCapabilities.load("http://remote:8000/v1", client=client)

        assert local.thinking_toggle is True
        assert remote == NOTHING

    def test_peek_never_asks(self) -> None:
        assert EndpointCapabilities.peek("http://h:1/v1") == NOTHING

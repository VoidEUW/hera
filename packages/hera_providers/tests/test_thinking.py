"""Asking a server what it will accept, for every server that answers.

Each of these is a small parser over somebody else's JSON, and each is a place where being wrong
is invisible: a model that answers "I accept `low, medium, high`" for a model that only takes
`high` looks exactly like one that is right, right up until every turn 400s. So the cases below
are mostly about the *absent* answers, which is the direction that is safe.

**Nothing here touches the network.** Every request goes through an ``httpx.MockTransport``.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from hera_providers.capabilities import EndpointCapabilities
from hera_providers.thinking import (
    NOTHING,
    Registry,
    gemini_thinking,
    litellm_thinking,
    ollama_thinking,
    openrouter_thinking,
)

Handler = Callable[[httpx.Request], httpx.Response]
MINICPM = "{%- if enable_thinking is defined %}<think>{%- endif %}"


@pytest.fixture(autouse=True)
def _no_shared_cache() -> None:
    Registry.forget()
    EndpointCapabilities.forget()


def client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def router_body(*models: dict[str, object]) -> dict[str, object]:
    return {"data": list(models)}


def router_model(model_id: str, **reasoning: object) -> dict[str, object]:
    return {"id": model_id, "reasoning": reasoning}


class TestOpenRouter:
    def test_a_published_vocabulary_is_taken_in_order(self) -> None:
        found = openrouter_thinking(
            router_body(router_model("a/b", supported_efforts=["low", "high"])), "a/b"
        )

        assert found.efforts == ("low", "high")
        assert found.shape == "values"
        assert found.source == "openrouter"

    def test_a_token_budget_is_reported_and_wins_the_shape(self) -> None:
        # OpenRouter sets `supports_max_tokens` on a model that wants an Anthropic-style budget.
        # Offering it `low/medium/high` would be a control that does nothing.
        found = openrouter_thinking(
            router_body(router_model("a/b", supports_max_tokens=True)), "a/b"
        )

        assert found.budget is True
        assert found.shape == "budget"
        assert found.toggle is True, "it is still a thing that can be reasoned with"

    def test_a_budget_model_may_also_list_efforts_and_the_list_wins(self) -> None:
        found = openrouter_thinking(
            router_body(
                router_model("a/b", supported_efforts=["low", "high"], supports_max_tokens=True)
            ),
            "a/b",
        )

        assert found.efforts == ("low", "high")
        assert found.budget is True
        assert found.shape == "values", "a list is the finer control"

    def test_a_reasoning_block_with_no_list_answers_nothing_drawable(self) -> None:
        # `default_effort: high` and nothing else says the model reasons and gives no values.
        # That is **not** enough for a switch: a switch writes `enable_thinking: false`, and
        # without the list we do not know that this model has an off position, or what it is.
        # Offering a control whose only setting we cannot express is the inert-control case.
        found = openrouter_thinking(router_body(router_model("a/b", default_effort="high")), "a/b")

        assert found.efforts == ()
        assert found.shape == "none"
        assert found.source == "openrouter", "it did answer -- just not with a control"

    def test_a_default_enabled_model_does_get_a_switch(self) -> None:
        # `default_enabled` is the difference: it says reasoning can be off, so the off position
        # exists even though no levels are published.
        found = openrouter_thinking(router_body(router_model("a/b", default_enabled=True)), "a/b")

        assert found.shape == "toggle"

    def test_a_model_that_does_not_reason_is_answered_not_unknown(self) -> None:
        # Two different things, and the settings screen is entitled to tell them apart: *the
        # server says this model does not reason* is not *nobody has told us anything*. Both
        # draw no control; only one of them is a claim.
        found = openrouter_thinking(router_body({"id": "a/b"}), "a/b")

        assert found == NOTHING.__class__(source="openrouter")
        assert found.known is False
        assert found.shape == "none"

    def test_a_model_the_catalogue_does_not_carry_is_unknown(self) -> None:
        found = openrouter_thinking(
            router_body(router_model("a/b", supported_efforts=["low"])), "c/d"
        )

        assert found.known is False

    def test_rubbish_is_unknown_rather_than_an_exception(self) -> None:
        rubbish: list[object] = [{}, {"data": "nonsense"}, {"data": [1, "two", None]}, [], None, 7]
        for payload in rubbish:
            assert openrouter_thinking(payload, "a/b").known is False

    def test_a_non_string_effort_is_dropped(self) -> None:
        found = openrouter_thinking(
            router_body(router_model("a/b", supported_efforts=["low", 7, None, "high"])), "a/b"
        )

        assert found.efforts == ("low", "high")


class TestGemini:
    def test_thinking_true_is_a_switch(self) -> None:
        found = gemini_thinking({"name": "models/x", "thinking": True})

        assert found == NOTHING.__class__(toggle=True, source="gemini")

    def test_thinking_false_is_not_a_switch(self) -> None:
        assert gemini_thinking({"thinking": False}).toggle is False

    def test_a_body_with_no_thinking_field_is_unknown(self) -> None:
        # Which is what the resource actually returns for a model that does not reason -- and
        # `false` and *absent* must not be confused, though both draw nothing.
        assert gemini_thinking({"name": "models/x", "inputTokenLimit": 10}).known is False

    def test_no_vocabulary_is_invented(self) -> None:
        # The guide once implied a `supportedThinkingLevels` array. There is none. This is here so
        # that adding one is a deliberate act rather than an accident of a doc rewrite.
        found = gemini_thinking({"thinking": True, "supportedThinkingLevels": ["low"]})

        assert found.efforts == ()


class TestLiteLLM:
    def test_a_supported_row_is_a_switch(self) -> None:
        found = litellm_thinking(
            {"data": [{"model_group": "a/b", "supports_reasoning": True}]}, "a/b"
        )

        assert found.toggle is True
        assert found.source == "litellm"

    def test_an_unsupported_row_is_not_a_switch(self) -> None:
        assert litellm_thinking({"data": [{"model_group": "a/b"}]}, "a/b").toggle is False

    def test_a_model_group_that_is_not_there_is_unknown(self) -> None:
        assert litellm_thinking({"data": [{"model_group": "x"}]}, "a/b").known is False


class TestOllama:
    def test_a_thinking_capability_is_a_switch(self) -> None:
        found = ollama_thinking({"capabilities": ["completion", "tools", "thinking"]})

        assert found.toggle is True
        assert found.source == "ollama"

    def test_its_absence_is_not_a_switch(self) -> None:
        # Which is the interesting case: a llama.cpp serving the same MiniCPM weights *does*
        # report a thinking switch, and Ollama does not. Each is right about itself, and matching
        # on the model id would have got one of them confidently wrong.
        assert ollama_thinking({"capabilities": ["completion", "tools"]}).toggle is False

    def test_rubbish_is_not_a_switch(self) -> None:
        rubbish: list[object] = [{}, {"capabilities": "thinking"}, [], None]
        for payload in rubbish:
            assert ollama_thinking(payload).toggle is False


class TestTheRegistry:
    async def test_an_openrouter_endpoint_is_asked_its_catalogue(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/api/v1/models")
            return httpx.Response(
                200, json=router_body(router_model("a/b", supported_efforts=["low", "high"]))
            )

        async with client(handler) as http:
            found = await Registry.resolve("openrouter", "https://x.test/v1", "a/b", client=http)

        assert found.efforts == ("low", "high")

    async def test_llamacpp_is_found_whatever_the_endpoint_was_called(self) -> None:
        # A llama.cpp registered as `openai` is still a llama.cpp server, and that is the ordinary
        # way somebody registers one. Gating on the kind would miss it.
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/props":
                return httpx.Response(
                    200,
                    json={"chat_template": MINICPM, "chat_template_caps": {}},
                )
            return httpx.Response(404)

        async with client(handler) as http:
            found = await Registry.resolve("openai", "http://127.0.0.1:8080/v1", "m", client=http)

        assert found.source == "llamacpp"
        assert found.toggle is True

    async def test_ollama_is_asked_on_its_native_api(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/show":
                return httpx.Response(200, json={"capabilities": ["completion", "thinking"]})
            return httpx.Response(404)

        async with client(handler) as http:
            found = await Registry.resolve(
                "ollama", "http://127.0.0.1:11434", "qwen3:4b", client=http
            )

        assert found.source == "ollama"
        assert found.toggle is True

    async def test_litellm_is_found_and_the_key_is_sent_to_it(self) -> None:
        seen: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/model_group/info":
                seen.append(request.headers.get("authorization"))
                return httpx.Response(
                    200, json={"data": [{"model_group": "a/b", "supports_reasoning": True}]}
                )
            return httpx.Response(404)

        async with client(handler) as http:
            found = await Registry.resolve(
                "generic", "http://gw.test", "a/b", api_key="sk-secret", client=http
            )

        assert found.source == "litellm"
        assert seen == ["Bearer sk-secret"]

    async def test_a_server_that_answers_nothing_leaves_the_declaration_standing(self) -> None:
        # The fallback that makes the ~17 prose-only providers usable at all.
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        async with client(handler) as http:
            found = await Registry.resolve(
                "openai",
                "https://api.openai.test/v1",
                "gpt-5-pro",
                client=http,
                declared=NOTHING.__class__(efforts=("high",), source="declared"),
            )

        assert found.source == "declared"
        assert found.efforts == ("high",)

    async def test_a_server_that_answers_outranks_a_declaration(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/api/v1/models"):
                return httpx.Response(
                    200, json=router_body(router_model("a/b", supported_efforts=["low", "high"]))
                )
            return httpx.Response(404)

        async with client(handler) as http:
            found = await Registry.resolve(
                "openrouter",
                "https://x.test/v1",
                "a/b",
                client=http,
                declared=NOTHING.__class__(efforts=("stale",), source="declared"),
            )

        assert found.source == "openrouter"
        assert found.efforts == ("low", "high")

    async def test_an_unreachable_server_is_unknown_and_not_an_exception(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        async with client(handler) as http:
            found = await Registry.resolve("openrouter", "https://x.test/v1", "a/b", client=http)

        assert found.known is False

    async def test_a_server_is_asked_once_within_the_hour(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if request.url.path.endswith("/api/v1/models"):
                return httpx.Response(
                    200, json=router_body(router_model("a/b", supported_efforts=["low"]))
                )
            return httpx.Response(404)

        async with client(handler) as http:
            for _ in range(3):
                await Registry.resolve("openrouter", "https://x.test/v1", "a/b", client=http)

        assert calls == 1

    async def test_two_models_on_one_endpoint_are_asked_separately(self) -> None:
        # Each model is its own question: one model appearing in a catalogue says nothing about
        # the other, and lumping them together is how a chat model inherits a coding model's
        # vocabulary.
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/api/v1/models"):
                return httpx.Response(
                    200,
                    json=router_body(
                        router_model("a/b", supported_efforts=["low"]),
                        router_model("c/d", supported_efforts=["max"]),
                    ),
                )
            return httpx.Response(404)

        async with client(handler) as http:
            first = await Registry.resolve("openrouter", "https://x.test/v1", "a/b", client=http)
            second = await Registry.resolve("openrouter", "https://x.test/v1", "c/d", client=http)

        assert first.efforts == ("low",)
        assert second.efforts == ("max",)

    def test_peek_never_asks(self) -> None:
        assert Registry.peek("openrouter", "https://x.test/v1", "a/b") == NOTHING


class TestShape:
    def test_nothing_draws_nothing(self) -> None:
        assert NOTHING.shape == "none"
        assert NOTHING.known is False

    def test_a_toggle_alone_is_a_toggle(self) -> None:
        assert NOTHING.__class__(toggle=True).shape == "toggle"

    def test_a_budget_alone_is_a_budget(self) -> None:
        assert NOTHING.__class__(budget=True).shape == "budget"

    def test_efforts_beat_a_budget_because_a_list_is_finer(self) -> None:
        assert NOTHING.__class__(efforts=("low",), budget=True).shape == "values"

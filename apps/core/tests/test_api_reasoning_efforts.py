"""What each model is reported as able to be told about its reasoning.

The interesting work is in :mod:`hera_providers.thinking`, which asks the servers; this file is
about the seam -- that whatever the registry answers is what lands on the response, and that a
model nobody could ask about is reported as unknown rather than as permissive.

**The registry is stubbed, deliberately.** The probes make real HTTP calls and are tested against
a ``MockTransport`` in ``packages/hera_providers/tests/test_thinking.py``; stubbing them here is
what keeps this file hermetic. An earlier version of it stubbed ``ReasoningEfforts.load`` and
stopped doing so when the route moved to the registry -- and the seven tests went from instant to
thirteen seconds, quietly reaching the real OpenRouter. A test that passes because the internet
cooperated is not a test.
"""

from __future__ import annotations

from typing import Any

import pytest
from core_support import API
from hera_providers.capabilities import NOTHING as CAPS_NOTHING
from hera_providers.capabilities import Capabilities, EndpointCapabilities, ToolCallShape
from hera_providers.thinking import NOTHING, Registry, Thinking
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def register(client: AsyncClient, name: str, kind: str, model_id: str) -> None:
    added = await client.post(
        f"{API}/providers",
        json={
            "name": name,
            "kind": kind,
            "base_url": f"http://localhost:4891/{name}/v1",
            "model_id": model_id,
        },
    )
    assert added.status_code == 201, added.text


def stub(monkeypatch: pytest.MonkeyPatch, answers: dict[str, Thinking]) -> None:
    """Make the registry answer `answers[model_id]`, and `NOTHING` for anything else.

    Keyed by model id, because that is what the registry is asked about -- a model id appearing in
    one endpoint's catalogue says nothing about another's, which is the whole reason the probes
    are per endpoint.
    """

    async def resolve(kind: str, base_url: str, model_id: str, **_: Any) -> Thinking:
        return answers.get(model_id, NOTHING)

    monkeypatch.setattr(Registry, "resolve", staticmethod(resolve))


def model_named(body: dict[str, Any], provider: str, model_id: str) -> dict[str, Any]:
    entry = next(p for p in body["providers"] if p["name"] == provider)
    return next(m for m in entry["models"] if m["id"] == model_id)


class TestWhatIsReported:
    async def test_a_published_vocabulary_arrives_as_a_picker(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The bug this exists for: `qwen/qwen3.8-27b` accepts `xhigh, medium, low` and rejects
        # `high`, which is one of the three values the composer used to offer every model.
        stub(
            monkeypatch,
            {"qwen/qwen3.8-27b": Thinking(efforts=("xhigh", "medium", "low"), source="openrouter")},
        )
        await register(client, "router", "openrouter", "qwen/qwen3.8-27b")

        model = model_named(
            (await client.get(f"{API}/providers")).json(), "router", "qwen/qwen3.8-27b"
        )

        assert model["reasoning_efforts"] == ["xhigh", "medium", "low"]
        assert model["thinking_shape"] == "values"
        assert model["thinking_source"] == "openrouter"

    async def test_a_thinking_switch_arrives_as_a_switch(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub(monkeypatch, {"MiniCPM5-2B": Thinking(toggle=True, source="llamacpp")})
        await register(client, "studio", "openai", "MiniCPM5-2B")

        model = model_named((await client.get(f"{API}/providers")).json(), "studio", "MiniCPM5-2B")

        assert model["reasoning_efforts"] == []
        assert model["thinking_toggle"] is True
        assert model["thinking_shape"] == "toggle"

    async def test_a_token_budget_is_its_own_shape(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The one most easily mistaken for the others: offering `low/medium/high` to a model
        # that wants `max_tokens` produces a control that does nothing.
        stub(
            monkeypatch,
            {"anthropic/claude-opus-4.6": Thinking(budget=True, toggle=True, source="openrouter")},
        )
        await register(client, "router", "openrouter", "anthropic/claude-opus-4.6")

        model = model_named(
            (await client.get(f"{API}/providers")).json(), "router", "anthropic/claude-opus-4.6"
        )

        assert model["thinking_budget"] is True
        assert model["thinking_shape"] == "budget"

    async def test_a_model_nobody_could_ask_about_is_unknown_and_not_permissive(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The self-hosted case: nothing answered, so no control. Every field has to say *absent*
        # rather than *allowed*, because the difference is a control that does nothing.
        stub(monkeypatch, {})
        await register(client, "studio", "openai", "somebody/private-build")

        model = model_named(
            (await client.get(f"{API}/providers")).json(), "studio", "somebody/private-build"
        )

        assert model["reasoning_efforts"] == []
        assert model["thinking_toggle"] is False
        assert model["thinking_budget"] is False
        assert model["thinking_shape"] == "none"

    async def test_a_declared_vocabulary_is_used_when_nothing_was_published(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The fallback for the ~17 providers whose vocabulary is prose. A server that published
        # would outrank this, so `resolve` is stubbed to return the declaration's shape here.
        async def resolve(kind: str, base_url: str, model_id: str, **_: Any) -> Thinking:
            return Thinking(efforts=("low", "high"), source="declared")

        monkeypatch.setattr(Registry, "resolve", staticmethod(resolve))
        await register(client, "openai-direct", "openai", "gpt-5-pro")

        model = model_named(
            (await client.get(f"{API}/providers")).json(), "openai-direct", "gpt-5-pro"
        )

        assert model["reasoning_efforts"] == ["low", "high"]
        assert model["thinking_source"] == "declared"

    async def test_every_model_carries_the_fields_even_when_unknown(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A response that omits a field is not the same as one that says `false`, and the
        # browser has to be able to tell them apart without a default.
        stub(monkeypatch, {})
        body = (await client.get(f"{API}/providers")).json()

        for entry in body["providers"]:
            for model in entry["models"]:
                assert {
                    "reasoning_efforts",
                    "thinking_toggle",
                    "thinking_budget",
                    "thinking_source",
                    "thinking_shape",
                    "tool_call_shape",
                } <= set(model)


class TestToolCallShapeOnTheWire:
    """The detection reaching the browser, and staying a report rather than a switch (#145).

    ``EndpointCapabilities`` is stubbed alongside the registry because the endpoint reads both: the
    thinking probe has already populated the capabilities cache for this ``base_url`` by the time
    the route asks, so the answer is free in production and absent here unless it is stubbed.
    """

    @staticmethod
    def stub_caps(monkeypatch: pytest.MonkeyPatch, shape: ToolCallShape) -> None:
        async def load(base_url: str, **_kwargs: Any) -> Capabilities:
            return Capabilities(tool_call_shape=shape)

        monkeypatch.setattr(EndpointCapabilities, "load", staticmethod(load))

    async def test_a_template_with_a_tools_path_says_so(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub(monkeypatch, {})
        self.stub_caps(monkeypatch, "template")
        await register(client, "studio", "openai", "MiniCPM5-2B")

        model = model_named((await client.get(f"{API}/providers")).json(), "studio", "MiniCPM5-2B")

        assert model["tool_call_shape"] == "template"

    async def test_a_server_declaring_no_says_none(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub(monkeypatch, {})
        self.stub_caps(monkeypatch, "none")
        await register(client, "studio", "openai", "MiniCPM5-2B")

        model = model_named((await client.get(f"{API}/providers")).json(), "studio", "MiniCPM5-2B")

        assert model["tool_call_shape"] == "none"

    async def test_silence_is_reported_as_unknown_not_as_none(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The one worth pinning. An endpoint that said nothing must not be reported as permissive,
        # because "we don't know" and "it works" are different facts and the interface is expected
        # to be able to tell them apart without a default.
        stub(monkeypatch, {})
        self.stub_caps(monkeypatch, CAPS_NOTHING.tool_call_shape)
        await register(client, "studio", "openai", "MiniCPM5-2B")

        model = model_named((await client.get(f"{API}/providers")).json(), "studio", "MiniCPM5-2B")

        assert model["tool_call_shape"] == "unknown"

    async def test_a_none_endpoint_still_offers_its_tools(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Reported, never acted on: nothing about the tools this model is offered changes on the
        # strength of the field, so a `none` answer is information and not a policy.
        stub(monkeypatch, {})
        self.stub_caps(monkeypatch, "none")
        await register(client, "studio", "openai", "MiniCPM5-2B")

        body = (await client.get(f"{API}/providers")).json()
        entry = next(p for p in body["providers"] if p["name"] == "studio")

        assert "MiniCPM5-2B" in [m["id"] for m in entry["models"]]

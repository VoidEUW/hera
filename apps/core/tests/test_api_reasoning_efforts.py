"""What each model says it accepts, carried on the response rather than asked for in the browser.

The composer's reasoning control is drawn from ``reasoning_efforts`` and from nothing else, so
what this file pins down is the shape of that list: present and correct where the endpoint has
answered, and **empty everywhere else** — because empty is the interface's word for *draw no
picker*, and a value the server refuses fails the whole request rather than the setting.

The catalogue is a network call, so these drive it through a stub rather than reaching
OpenRouter, and the two cases that must never be enriched are the point: a self-hosted endpoint
whose model id happens to appear in somebody else's catalogue, and a model the catalogue does not
carry.
"""

from __future__ import annotations

import httpx
import pytest
from core_support import API
from httpx import AsyncClient

from hera_providers import ReasoningEfforts

pytestmark = pytest.mark.anyio

CATALOGUE = {
    "data": [
        {
            "id": "qwen/qwen3.8-27b",
            "reasoning": {
                "supported_efforts": ["xhigh", "medium", "low"],
                "default_effort": "xhigh",
            },
        },
        {
            "id": "stealth/space-bunny-alpha",
            "reasoning": {
                "mandatory": True,
                "supported_efforts": ["max", "xhigh", "high", "medium", "low"],
                "default_effort": "max",
            },
        },
        # Carries a reasoning block but never says which values it takes.
        {"id": "someone/quiet", "reasoning": {"default_effort": "high"}},
    ]
}


@pytest.fixture(autouse=True)
def catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer the catalogue from a stub, and leave nothing cached behind."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models"), "the catalogue is one endpoint, not a search"
        return httpx.Response(200, json=CATALOGUE)

    # Captured before the patch: the stub drives the real loader through a mock transport, which
    # is the only way to exercise the fetch, the cache and the failure handling without a network.
    real_load = ReasoningEfforts.load

    async def fake_load(*_args: object, **kwargs: object) -> dict[str, tuple[str, ...]]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await real_load(client=client, **kwargs)
        finally:
            await client.aclose()

    monkeypatch.setattr(ReasoningEfforts, "load", staticmethod(fake_load))
    ReasoningEfforts.forget()


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


class TestTheEffortsAModelAccepts:
    async def test_an_openrouter_model_carries_its_own_values(self, client: AsyncClient) -> None:
        # The bug this exists for: `qwen/qwen3.8-27b` rejects `high`, which is one of the three
        # values the composer used to offer every model regardless.
        await register(client, "router", "openrouter", "qwen/qwen3.8-27b")

        providers = (await client.get(f"{API}/providers")).json()["providers"]
        model = next(p for p in providers if p["name"] == "router")["models"][0]

        assert model["reasoning_efforts"] == ["xhigh", "medium", "low"]

    async def test_a_registered_variant_suffix_still_matches(self, client: AsyncClient) -> None:
        # `:free` is what a person types; the catalogue lists the model bare.
        await register(client, "router", "openrouter", "qwen/qwen3.8-27b:free")

        providers = (await client.get(f"{API}/providers")).json()["providers"]
        model = next(p for p in providers if p["name"] == "router")["models"][0]

        assert model["reasoning_efforts"] == ["xhigh", "medium", "low"]

    async def test_a_mandatory_reasoning_model_still_reports_its_whole_range(
        self, client: AsyncClient
    ) -> None:
        # `mandatory` says the model always reasons; it does not narrow what may be asked for.
        await register(client, "bunny", "openrouter", "stealth/space-bunny-alpha")

        providers = (await client.get(f"{API}/providers")).json()["providers"]
        model = next(p for p in providers if p["name"] == "bunny")["models"][0]

        assert model["reasoning_efforts"] == ["max", "xhigh", "high", "medium", "low"]


class TestWhereThereIsNoAnswer:
    async def test_a_self_hosted_model_is_never_enriched(self, client: AsyncClient) -> None:
        # The catalogue knows this id. That is not evidence about *this* endpoint, which is a
        # llama.cpp on loopback, and offering values it does not accept fails every turn.
        await register(client, "studio", "llamacpp", "qwen/qwen3.8-27b")

        providers = (await client.get(f"{API}/providers")).json()["providers"]
        model = next(p for p in providers if p["name"] == "studio")["models"][0]

        assert model["reasoning_efforts"] == []

    async def test_a_model_the_catalogue_does_not_carry_is_empty(self, client: AsyncClient) -> None:
        await register(client, "studio", "openrouter", "somebody/private-build")

        providers = (await client.get(f"{API}/providers")).json()["providers"]
        model = next(p for p in providers if p["name"] == "studio")["models"][0]

        assert model["reasoning_efforts"] == []

    async def test_a_model_that_never_says_which_values_is_empty(self, client: AsyncClient) -> None:
        # It publishes a default effort. A default is one value, not the set, and treating it as
        # the set would hide every other effort the model actually takes.
        await register(client, "router", "openrouter", "someone/quiet")

        providers = (await client.get(f"{API}/providers")).json()["providers"]
        model = next(p for p in providers if p["name"] == "router")["models"][0]

        assert model["reasoning_efforts"] == []

    async def test_the_seeded_local_endpoint_still_answers(self, client: AsyncClient) -> None:
        # Whatever the catalogue says, an install with one local endpoint must keep working.
        body = (await client.get(f"{API}/providers")).json()

        assert body["providers"]
        assert all("reasoning_efforts" in m for p in body["providers"] for m in p["models"])

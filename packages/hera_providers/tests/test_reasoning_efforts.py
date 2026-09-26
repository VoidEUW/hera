"""What a model accepts, asked of the endpoint rather than guessed from its id.

``reasoning_effort`` values are not a shared vocabulary. OpenRouter's set carries ``minimal``,
``none`` and ``xhigh``; ``qwen/qwen3.8-27b`` takes ``xhigh``, ``medium`` and ``low`` and
**rejects** ``high``. A control offering a value the server refuses fails the whole request, not
just the setting, so every uncertain case in here has to answer *unknown* — which the interface
reads as "draw no picker" — and never a guess.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from hera_providers.catalogue import ReasoningEfforts, catalogue_id, parse


@pytest.fixture(autouse=True)
def _no_shared_cache() -> None:
    """The cache is process-wide on purpose, and has to not leak between tests."""
    ReasoningEfforts.forget()


def body(*entries: dict[str, object]) -> dict[str, object]:
    return {"data": list(entries)}


def model(model_id: str, efforts: object = None, **extra: object) -> dict[str, object]:
    reasoning: dict[str, object] = dict(extra)
    if efforts is not None:
        reasoning["supported_efforts"] = efforts
    return {"id": model_id, "reasoning": reasoning}


class TestCatalogueId:
    def test_a_routing_variant_is_stripped(self) -> None:
        # What a person actually types: the free tier of a model the catalogue lists bare.
        assert catalogue_id("qwen/qwen3.8-27b:free") == "qwen/qwen3.8-27b"
        assert catalogue_id("qwen/qwen3.8-27b:nitro") == "qwen/qwen3.8-27b"

    def test_an_ordinary_id_is_left_alone(self) -> None:
        assert catalogue_id("stealth/space-bunny-alpha") == "stealth/space-bunny-alpha"
        assert catalogue_id("qwen/qwen3.8-27b") == "qwen/qwen3.8-27b"

    def test_a_bare_id_has_no_vendor_prefix_to_strip_towards(self) -> None:
        # Somebody's own naming. Splitting it would invent an id nobody publishes.
        assert catalogue_id("qwen3-8-27b") == "qwen3-8-27b"
        assert catalogue_id("minicpm5-2b:q8_0") == "minicpm5-2b:q8_0"


class TestParse:
    def test_efforts_are_kept_in_the_order_the_endpoint_published(self) -> None:
        found = parse(body(model("a/b", ["low", "xhigh", "high"])))

        assert found["a/b"] == ("low", "xhigh", "high")

    def test_a_model_with_no_reasoning_block_is_absent(self) -> None:
        assert parse(body({"id": "a/b"})) == {}

    def test_a_reasoning_block_with_no_efforts_is_absent(self) -> None:
        # It says reasoning is mandatory and what the default is, but not what is accepted. The
        # default is one value, not the set, and treating it as the set would hide the other two.
        assert parse(body(model("a/b", default_effort="high"))) == {}

    def test_garbage_in_is_unknown_rather_than_an_exception(self) -> None:
        rubbish: list[object] = [
            {},
            {"data": "nonsense"},
            {"data": [1, "two", None]},
            [],
            "nonsense",
            None,
        ]
        for payload in rubbish:
            assert parse(payload) == {}

    def test_a_non_string_effort_is_dropped_and_the_rest_kept(self) -> None:
        found = parse(body(model("a/b", ["low", 7, None, "high", ""])))

        assert found["a/b"] == ("low", "high")

    def test_duplicates_are_collapsed_keeping_first_position(self) -> None:
        assert parse(body(model("a/b", ["high", "low", "high"])))["a/b"] == ("high", "low")

    def test_an_empty_effort_list_is_absent(self) -> None:
        # Nothing accepted is not the same as anything accepted.
        assert parse(body(model("a/b", []))) == {}


Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> httpx.AsyncClient:
    """A client whose transport answers from a function, so no test opens a socket."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestLookup:
    def test_the_variant_suffix_still_finds_the_model(self) -> None:
        found = parse(body(model("qwen/qwen3.8-27b", ["xhigh", "medium", "low"])))

        assert ReasoningEfforts.for_model(found, "qwen/qwen3.8-27b:free") == (
            "xhigh",
            "medium",
            "low",
        )

    def test_an_unknown_model_is_empty_which_means_no_control(self) -> None:
        assert ReasoningEfforts.for_model({}, "qwen/qwen3.8-27b") == ()

    def test_a_model_the_catalogue_carries_without_efforts_is_also_empty(self) -> None:
        # Not a special case at the call site: absent and empty are the same answer, because both
        # mean nobody has said what this model accepts.
        found = parse(body(model("a/b", default_effort="high")))

        assert ReasoningEfforts.for_model(found, "a/b") == ()


class TestLoading:
    async def test_a_body_is_fetched_and_remembered(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=body(model("a/b", ["low", "high"])))

        async with _client(handler) as client:
            first = await ReasoningEfforts.load(client=client)
            second = await ReasoningEfforts.load(client=client)

        assert first["a/b"] == ("low", "high")
        assert second["a/b"] == ("low", "high")
        assert calls == 1, "a second call inside the hour should be answered from the cache"

    async def test_a_failure_is_an_empty_catalogue_and_not_an_exception(self) -> None:
        # A convenience that can turn a settings screen into a 500 is not a convenience. Losing
        # the control is survivable; not being able to open Settings is not.
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route to host")

        async with _client(handler) as client:
            found = await ReasoningEfforts.load(client=client)

        assert found == {}
        assert ReasoningEfforts.for_model(found, "a/b") == ()

    async def test_a_failure_is_cached_too(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ConnectError("no route to host")

        async with _client(handler) as client:
            await ReasoningEfforts.load(client=client)
            await ReasoningEfforts.load(client=client)

        assert calls == 1, "an endpoint that is down should not be retried on every request"

    async def test_a_body_that_is_not_json_is_an_empty_catalogue(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>gateway timeout</html>")

        async with _client(handler) as client:
            assert await ReasoningEfforts.load(client=client) == {}

    async def test_a_non_2xx_is_an_empty_catalogue(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json=body())

        async with _client(handler) as client:
            assert await ReasoningEfforts.load(client=client) == {}

    async def test_peek_never_fetches(self) -> None:
        # The path that must not block: a response being assembled while the network is
        # unavailable reads whatever was learned last, and `()` when there was never anything.
        def handler(_request: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("peek must not touch the network")

        async with _client(handler):
            assert ReasoningEfforts.peek() == {}

"""The DuckDuckGo adapter.

Scraped output, so the tests are mostly about what happens when the shape is not what was
promised — a row with no link, a field that is missing, an engine that refuses. The network is
never touched: `ddgs` is called through one seam (`DuckDuckGo._fetch`) and that is what these
replace, which keeps the thing under test the *mapping* rather than somebody's HTML.
"""

from __future__ import annotations

from typing import Any

import pytest
from ddgs.exceptions import RatelimitException

from hera_core.search import DuckDuckGo, SearchUnavailable


def rows(*items: dict[str, Any]) -> list[dict[str, Any]]:
    return list(items)


def answering(monkeypatch: pytest.MonkeyPatch, result: list[dict[str, Any]]) -> DuckDuckGo:
    engine = DuckDuckGo()
    monkeypatch.setattr(DuckDuckGo, "_fetch", lambda _self, _query, _limit: result)
    return engine


async def test_a_row_becomes_a_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = answering(
        monkeypatch,
        rows({"title": "Kerberos", "href": "https://example.test/k", "body": "A protocol."}),
    )

    hits = await engine.search("kerberos", limit=5)

    assert [(hit.title, hit.url, hit.snippet) for hit in hits] == [
        ("Kerberos", "https://example.test/k", "A protocol.")
    ]


async def test_a_row_with_no_link_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A result she cannot cite is worse than one result fewer."""
    engine = answering(
        monkeypatch, rows({"title": "Kerberos", "href": "", "body": "x"}, {"href": "  "})
    )

    assert await engine.search("kerberos", limit=5) == []


async def test_missing_fields_do_not_crash_the_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    """This is somebody else's HTML on the other end. A field that stopped being there should
    cost a snippet, not the answer."""
    engine = answering(monkeypatch, rows({"href": "https://example.test/k"}))

    hit = (await engine.search("kerberos", limit=5))[0]

    assert hit.url == "https://example.test/k"
    assert hit.title == ""
    assert hit.snippet == ""


async def test_a_snippet_is_collapsed_onto_one_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scraped snippets arrive with the source page's line breaks in them, and a result block
    that wraps unpredictably is the thing that makes a model quote the wrong page."""
    engine = answering(
        monkeypatch,
        rows({"title": "K", "href": "https://example.test/k", "body": " a\n  b \t c\n"}),
    )

    assert (await engine.search("k", limit=5))[0].snippet == "a b c"


async def test_an_engine_that_refused_is_told_apart_from_one_that_found_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The distinction the whole design rests on: `hera_mcp` turns a raise into a failed result
    and an empty list into "no results", and a model reacts differently to each."""
    engine = DuckDuckGo()

    def refuse(_self: DuckDuckGo, _query: str, _limit: int) -> list[dict[str, Any]]:
        raise RatelimitException("too many requests")

    monkeypatch.setattr(DuckDuckGo, "_fetch", refuse)

    with pytest.raises(SearchUnavailable, match="too many requests"):
        await engine.search("kerberos", limit=5)


async def test_nothing_found_is_an_empty_list_and_not_a_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert await answering(monkeypatch, []).search("asdkjhq", limit=5) == []


async def test_the_search_does_not_block_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ddgs` is synchronous and does real network I/O. Called on the loop it would stall every
    other conversation in the process for as long as the search took."""
    import asyncio
    import threading

    loop_thread = threading.get_ident()
    seen: list[int] = []

    def record(_self: DuckDuckGo, _query: str, _limit: int) -> list[dict[str, Any]]:
        seen.append(threading.get_ident())
        return []

    monkeypatch.setattr(DuckDuckGo, "_fetch", record)
    await DuckDuckGo().search("kerberos", limit=5)

    assert seen and seen[0] != loop_thread
    assert asyncio.get_running_loop() is not None


@pytest.mark.live
async def test_it_really_searches() -> None:
    """Against DuckDuckGo itself. Marked ``live`` and never run in CI — it is the only check
    that the scraped shape `ddgs` returns is still the shape this module maps, which is exactly
    the thing no amount of stubbing can tell us."""
    hits = await DuckDuckGo().search("kerberos ticket granting ticket", limit=3)

    assert hits, "the engine answered with nothing at all"
    assert all(hit.url.startswith("http") for hit in hits)
    assert any(hit.title for hit in hits)

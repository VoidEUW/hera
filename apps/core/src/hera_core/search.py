"""Looking things up, over DuckDuckGo.

The adapter behind :class:`hera_mcp.Searcher`. It lives here rather than in ``hera_mcp`` for
the reason every adapter does: which engine a person's questions are sent to is a decision about
*this deployment*, and the server she is should not have an opinion about it. Swapping this for
a self-hosted SearXNG, or for something with an API key behind it, is a class in this module and
one line in :mod:`hera_core.wiring` — nothing in her tool description changes, because nothing
in it mentions DuckDuckGo.

**Why DuckDuckGo first.** It is the only one that needs no key, and a search that only works
after somebody has signed up somewhere is not an answer to the problem search exists to solve —
a fresh install that cannot look anything up has a model that invents things fluently
(``docs/tooling.md`` § 1).

``ddgs`` is synchronous and does real network I/O, so every call goes through a worker thread.
Calling it directly from the event loop would stall every other conversation in the process for
as long as the search took, which on a bad day is the timeout.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from ddgs import DDGS
from ddgs.exceptions import DDGSException

from hera_mcp import Hit

__all__ = ["DuckDuckGo"]


class DuckDuckGo:
    """Text search over DuckDuckGo, with no account and no key.

    One client is reused across calls: ``ddgs`` keeps a connection pool and a set of cookies
    behind it, and building a fresh one per search is both slower and more likely to be
    rate-limited.
    """

    def __init__(self, *, timeout: int = 12, region: str = "wt-wt") -> None:
        self._client = DDGS(timeout=timeout)
        self._region = region
        """``wt-wt`` is "no region": results are not bent towards wherever the server happens to
        be hosted, which for a self-hosted assistant is the less surprising default. Her answers
        are in the language her `language` mind region says, and that is a separate question
        from which country's results she is shown."""

    async def search(self, query: str, *, limit: int) -> Sequence[Hit]:
        try:
            rows = await asyncio.to_thread(self._fetch, query, limit)
        except DDGSException as cause:
            # Read by the model, so it says what to do about it. Distinguishable from "no
            # results", which is a normal answer and not raised at all.
            raise SearchUnavailable(f"the search engine did not answer: {cause}") from cause
        return [hit for hit in (_hit(row) for row in rows) if hit is not None]

    def _fetch(self, query: str, limit: int) -> list[dict[str, Any]]:
        return self._client.text(query, region=self._region, max_results=limit)


class SearchUnavailable(RuntimeError):
    """The engine failed. Kept apart from an empty result on purpose: a model told that a
    search is broken stops searching, and a model told nothing was found tries other words."""


def _hit(row: dict[str, Any]) -> Hit | None:
    """One row of ``ddgs`` output as a :class:`~hera_mcp.Hit`, or ``None`` if it is not usable.

    Defensive about the shape because it is scraped rather than served: this is somebody's HTML
    on the other end, and a row missing its link is worth dropping rather than showing her a
    result she cannot cite.
    """
    url = str(row.get("href") or "").strip()
    if not url:
        return None
    return Hit(
        title=str(row.get("title") or "").strip(),
        url=url,
        snippet=" ".join(str(row.get("body") or "").split()),
    )

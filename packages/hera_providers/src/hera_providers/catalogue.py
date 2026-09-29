"""What reasoning efforts a model actually accepts, asked of the endpoint rather than guessed.

``reasoning_effort`` is an OpenAI-shaped request field with no shared meaning. It is one of the
pass-through options ADR 18 is about -- a field the *server* understands and this project does
not -- and the values are not the same set everywhere. OpenAI's are ``low``/``medium``/``high``;
OpenRouter's catalogue includes ``minimal``, ``none`` and ``xhigh``; and individual models accept
a subset of even that. ``qwen/qwen3.8-27b`` takes ``xhigh``, ``medium`` and ``low`` and **rejects
``high``**. A picker that offers the OpenAI three therefore does not merely fail to help -- picking
"high" on that model sends a value its server refuses, and the refusal is the whole request.

So the set is fetched from whoever will enforce it. OpenRouter publishes it per model at
``/api/v1/models``, under ``reasoning.supported_efforts``, alongside ``default_effort`` and a
``mandatory`` flag. Of 458 models, 326 carry a ``reasoning`` block and 186 enumerate their
efforts; the rest are reported as *unknown*, which means **no picker** rather than a guess.

**This is not the catalogue ADR 18 refuses.** That decision objects to a schema *we* write, which
is then wrong about every server it was not written against. This is the opposite: the endpoint
is asked what it accepts, per model, and answers in its own vocabulary. Nothing here inspects a
model id to decide what a model is -- ``qwen3-8-27b``, ``Qwen3.8-27B`` and a vendor's own
spelling are the same lookup failing three ways, and a match that guessed would be worse than no
match at all.

**Only for endpoints that are OpenRouter.** A model id appearing in OpenRouter's catalogue says
nothing about what a self-hosted llama.cpp will accept, and the id is the only thing the two would
be matched on. ``caller`` is what decides, and it must be the endpoint's declared kind.
"""

from __future__ import annotations

import asyncio
import time

import httpx

CATALOGUE_URL = "https://openrouter.ai/api/v1/models"

#: How long a fetched catalogue is good for. The list moves slowly and the answer only decides
#: which buttons to draw, so a stale hour is better than a request per page load. An empty
#: catalogue is cached too, and for the same length: a catalogue that could not be fetched should
#: not become a request on every keystroke either.
TTL_SECONDS = 3600.0

#: OpenRouter appends a routing variant to the id -- ``qwen/qwen3.8-27b:free`` is the same model
#: as ``qwen/qwen3.8-27b`` served on a free tier, and only the first is in the catalogue. Ids that
#: carry no ``/`` are not ours to split: a bare ``qwen3-8-27b`` is somebody's own naming and has
#: no vendor prefix to strip towards.
VARIANT_SEPARATOR = ":"

Efforts = dict[str, tuple[str, ...]]


def catalogue_id(model_id: str) -> str:
    """The id to look up, with a routing variant suffix removed.

    A no-op for the overwhelming majority of ids, and deliberately shallow: it splits on the last
    ``:`` only when there is a ``/`` before it, so ``stealth/space-bunny-alpha`` and
    ``openbmb/minicpm5-2b:q8_0`` are both left alone until the caller decides the endpoint is
    OpenRouter's to answer for.
    """
    if "/" not in model_id:
        return model_id
    head, separator, _tail = model_id.rpartition(VARIANT_SEPARATOR)
    if separator and head and VARIANT_SEPARATOR not in head:
        return head
    return model_id


def parse(payload: object) -> Efforts:
    """The supported efforts per model id, from a ``/models`` body.

    Tolerant by construction. A model with no ``reasoning`` block, or a block with no
    ``supported_efforts``, is simply absent from the result -- which the caller reads as *unknown*
    and answers by drawing no picker. That is the only safe direction: a missing entry costs a
    control, and a wrong one costs a rejected request on every turn.
    """
    found: Efforts = {}
    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return found
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        reasoning = entry.get("reasoning")
        if not isinstance(model_id, str) or not isinstance(reasoning, dict):
            continue
        efforts = reasoning.get("supported_efforts")
        if not isinstance(efforts, list):
            continue
        # Order kept as published, and duplicates dropped: it is the order the endpoint considers
        # ascending, and it is the order the buttons should be drawn in.
        seen: list[str] = []
        for effort in efforts:
            if isinstance(effort, str) and effort and effort not in seen:
                seen.append(effort)
        if seen:
            found[model_id] = tuple(seen)
    return found


class ReasoningEfforts:
    """The catalogue, fetched at most once per :data:`TTL_SECONDS` and remembered.

    Process-wide, and cached as a plain attribute rather than anything clever: there is one
    answer, every request wants the same one, and a lock is only worth having because two
    requests arriving together would otherwise both fetch 458 models. That is a real cost twice,
    so the lock is held across the fetch and released before anyone waits on it.
    """

    _cached: Efforts | None = None
    _fetched_at: float = 0.0
    _lock: asyncio.Lock | None = None

    @classmethod
    def _guard(cls) -> asyncio.Lock:
        # Built on first use rather than at import: an asyncio.Lock created at module scope binds
        # to whichever loop was running then, and this process serves requests on more than one.
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def peek(cls) -> Efforts:
        """What is already known, without waiting for or attempting a fetch.

        For the path that must not block: a response being assembled while the network is
        unavailable should carry whatever was learned last, and if that is nothing then the model
        is unknown.
        """
        return cls._cached or {}

    @classmethod
    def forget(cls) -> None:
        """Drop the cache. For tests, and for a person who has just registered a new endpoint."""
        cls._cached = None
        cls._fetched_at = 0.0

    @classmethod
    async def load(cls, *, client: httpx.AsyncClient | None = None) -> Efforts:
        """The catalogue, fetching it if this is the first ask or the last one has gone stale.

        Never raises. A catalogue is a convenience -- it decides which buttons a screen draws --
        and a failed fetch has to leave the interface working with fewer controls rather than
        turn a settings screen into an error. An unreachable OpenRouter is reported as an empty
        catalogue and retried an hour later.
        """
        if cls._cached is not None and time.monotonic() - cls._fetched_at < TTL_SECONDS:
            return cls._cached

        async with cls._guard():
            # Checked again inside the lock: a second request that queued behind the first should
            # use its result rather than start a second fetch of the same thing.
            if cls._cached is not None and time.monotonic() - cls._fetched_at < TTL_SECONDS:
                return cls._cached
            try:
                owns = client is None
                http = client or httpx.AsyncClient(timeout=10.0)
                try:
                    answer = await http.get(CATALOGUE_URL)
                    answer.raise_for_status()
                    found = parse(answer.json())
                finally:
                    if owns:
                        await http.aclose()
            except (httpx.HTTPError, ValueError):
                found = {}
            cls._cached = found
            cls._fetched_at = time.monotonic()
            return found

    @classmethod
    def for_model(cls, catalogue: Efforts, model_id: str) -> tuple[str, ...]:
        """The efforts one model accepts, or ``()`` for *do not draw a picker*.

        ``()`` is the answer for a model the catalogue does not carry, for one that carries no
        effort list, and for an id that could not be matched. They are deliberately
        indistinguishable: all three mean the same thing, which is that nobody has said what this
        model accepts and Hera is not going to guess.
        """
        return catalogue.get(catalogue_id(model_id), ())

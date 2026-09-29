"""What a model can be told about its reasoning, asked of whoever is serving it.

There are three answers, and they are not the same shape:

- **a list of values** -- ``reasoning_effort: high``. Only one provider on earth publishes this
  over HTTP (see ``OpenRouter`` below), because a gateway is the only kind of server that
  validates a request against many vendors' schemas at once and therefore the only kind that
  knows the union.
- **a boolean** -- ``enable_thinking: true``. What most reasoning models actually want. Qwen, GLM,
  DeepSeek, MiniCPM and Kimi are all Think/No Think, and the enum does not exist for them.
- **a token budget** -- ``max_tokens`` on a thinking block. What Anthropic-shaped models want, and
  a number rather than a named level.

A picker can only be built from the first, a switch only from the second, and a stepper only from
the third. Drawing the wrong one produces a control that silently does nothing, so **which** of
the three a model has is the whole of this module, and ``nothing`` is a first-class answer.

**Where each answer comes from, in the order it is trusted:**

1. **Asked.** Five servers publish something: OpenRouter, llama.cpp, Ollama, LiteLLM, Gemini.
2. **Declared.** For the rest -- OpenAI, Anthropic, xAI, DeepSeek, Groq, Perplexity, Meta,
   Mistral, Fireworks, Baseten, Cerebras, Azure, Cohere, AI21, Alibaba, Z.ai, Moonshot -- the
   vocabulary is published in documentation prose and nowhere else. There is no endpoint to ask,
   and a docs scraper would be *worse* than a table: a silently mis-parsed table is
   indistinguishable from a correct one, and it breaks on every docs redesign. So the person
   states it once, on Settings -> Models, and it is remembered per model in ``config.toml`` --
   which is the arrangement ADR 18 describes for presets, applied to the case it did not consider.
3. **Nothing.** No control is drawn, and the field stays hand-writable. A wrong control is worse
   than an absent one, and so is a plausible one.

**Never matched from a model id.** ``gpt-5-pro`` accepts ``high`` and nothing else, while
``gpt-5.1-codex-max`` adds ``xhigh``; ``qwen3.8-27b`` takes ``xhigh, medium, low`` and rejects
``high``. An id is a string somebody typed, and three spellings of one model are three chances to
be wrong in a way that only shows up as a rejected request. That is the argument ADR 18 makes,
and nothing here weakens it.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import ClassVar, NamedTuple

import httpx

from hera_providers.capabilities import EndpointCapabilities, props_url

#: The three shapes, as one answer. Every field defaults to the *absent* answer rather than the
#: permissive one, because ``()``/``False`` is what a control is not drawn from.
DEFAULT_TTL = 3600.0


class Thinking(NamedTuple):
    """What one model can be told about its reasoning."""

    efforts: tuple[str, ...] = ()
    """Named levels, ascending, exactly as published. Empty means no picker."""

    toggle: bool = False
    """Whether an on/off thinking switch would reach the model. Empty means no switch."""

    budget: bool = False
    """Whether the model wants a thinking *token budget* rather than a named level. A third
    control shape, and the one most easily mistaken for the other two: offering ``low/medium/high``
    to a model that wants ``budget_tokens`` produces a control that does nothing."""

    source: str = ""
    """Which of the three sources answered, for display on the settings screen. A person looking
    at a control deserves to know whether the server said so or they did."""

    @property
    def known(self) -> bool:
        """Whether anything at all is known. The only thing that means *draw no control*."""
        return bool(self.efforts) or self.toggle or self.budget

    @property
    def shape(self) -> str:
        """Which control this model wants: ``values``, ``toggle``, ``budget`` or nothing.

        Values win over a toggle when a server publishes both, because a list is the finer
        control and the switch is what it stands in for. A budget wins over a toggle, for the
        same reason: if a model wants a number, an on/off is a number with two values and no
        way to reach the middle.
        """
        if self.efforts:
            return "values"
        if self.budget:
            return "budget"
        if self.toggle:
            return "toggle"
        return "none"


NOTHING = Thinking(source="none")

OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"
GEMINI_MODELS = "{root}/models/{model}"


# -- OpenRouter: the only publisher of a value list ---------------------------------------


def openrouter_thinking(payload: object, model_id: str) -> Thinking:
    """One model's reasoning answer, from an OpenRouter ``/models`` body.

    Two fields and not one, because OpenRouter signals a *shape* as well as a vocabulary:
    ``supports_max_tokens`` is set on a model that wants an Anthropic-style thinking budget, and
    drawing a picker for such a model produces exactly the inert control this package exists to
    avoid. A model can want both, and then both are reported -- which is why ``budget`` does not
    suppress ``efforts``.
    """
    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return NOTHING
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("id") != model_id:
            continue
        reasoning = entry.get("reasoning")
        if not isinstance(reasoning, dict):
            return Thinking(source="openrouter")
        values = reasoning.get("supported_efforts")
        efforts = (
            tuple(v for v in values if isinstance(v, str) and v) if isinstance(values, list) else ()
        )
        budget = reasoning.get("supports_max_tokens") is True
        # A `reasoning` block with no `supported_efforts` is a model that reasons and does not
        # publish a vocabulary -- so it gets the switch, not a picker, and never an empty picker.
        toggle = bool(efforts) or budget or reasoning.get("default_enabled") is True
        return Thinking(efforts=efforts, toggle=toggle, budget=budget, source="openrouter")
    return NOTHING


# -- Gemini: a boolean, and the only probe that needs a differently-shaped request ----------


def gemini_thinking(payload: object) -> Thinking:
    """A Gemini ``Model`` body.

    The full resource is ``name, baseModelId, version, displayName, description,
    inputTokenLimit, outputTokenLimit, supportedGenerationMethods[], thinking, temperature,
    maxTemperature, topP, topK`` -- one boolean and no vocabulary. Worth having checked for a
    ``supportedThinkingLevels`` array, which the guide once implied; there is none, and a
    Gemini picker would have to be a hand-written table.
    """
    if not isinstance(payload, dict):
        return NOTHING
    thinking = payload.get("thinking")
    if thinking is True:
        return Thinking(toggle=True, source="gemini")
    if thinking is False:
        return Thinking(source="gemini")
    return NOTHING


# -- LiteLLM: a boolean, and it fronts a hundred providers -------------------------------


def litellm_thinking(payload: object, model_id: str) -> Thinking:
    """A LiteLLM ``/model_group/info`` body.

    LiteLLM is a proxy, so this is the cheapest way to cover a hundred vendors at once -- but it
    reports a boolean and nothing more, so what it buys is "this model reasons", not which levels
    it takes.
    """
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return NOTHING
    for row in rows:
        if not isinstance(row, dict) or row.get("model_group") != model_id:
            continue
        if row.get("supports_reasoning") is True:
            return Thinking(toggle=True, source="litellm")
        return Thinking(source="litellm")
    return NOTHING


# -- Ollama: a boolean, per model, on the native API --------------------------------------


def ollama_thinking(payload: object) -> Thinking:
    """An Ollama ``/api/show`` body.

    ``capabilities`` is an array of strings and ``"thinking"`` is one of them. Newer Ollama builds
    also document a ``thinking.values`` list, which would be a vocabulary; 0.16.3 does not return
    one, so this stays a boolean and the absence is not read as an empty answer to a question the
    server never answered.
    """
    if not isinstance(payload, dict):
        return NOTHING
    capabilities = payload.get("capabilities")
    if isinstance(capabilities, list) and "thinking" in capabilities:
        return Thinking(toggle=True, source="ollama")
    return Thinking(source="ollama")


# -- the registry -------------------------------------------------------------------------


class Registry:
    """Every probe, and the answer they add up to.

    Probes are keyed by the endpoint kind, except ``/props`` and ``/model_group/info``, which are
    keyed by nothing: a llama.cpp registered as ``openai`` is still a llama.cpp server, and LiteLLM
    can front anything. Both answer 404 where they are absent, which is a whole answer rather than
    a failure, and both are cached per ``base_url`` so the question is asked at most once an hour.
    """

    _cache: ClassVar[dict[tuple[str, str], tuple[float, Thinking]]] = {}
    _lock: ClassVar[asyncio.Lock | None] = None

    @classmethod
    def _guard(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def forget(cls) -> None:
        """Drop everything remembered. For tests."""
        cls._cache.clear()
        EndpointCapabilities.forget()

    @classmethod
    def peek(cls, kind: str, base_url: str, model_id: str) -> Thinking:
        """What is already known, without asking anything.

        Never raises and never fetches. A failure anywhere leaves the previous answer in place,
        and if there was never one then ``NOTHING`` -- which draws no control, the safe direction.
        """
        entry = cls._cache.get((kind, _key(base_url, model_id)))
        return entry[1] if entry is not None else NOTHING

    @classmethod
    async def resolve(
        cls,
        kind: str,
        base_url: str,
        model_id: str,
        *,
        api_key: str = "",
        declared: Thinking = NOTHING,
        client: httpx.AsyncClient | None = None,
    ) -> Thinking:
        """What this model can be told, asked first and falling back to what the person declared.

        ``declared`` is what a person entered on Settings -> Models, and it is only consulted
        when no probe answered. That ordering is the point: a server that says what it accepts
        is more reliable than anything anybody remembers, and a person who declared a vocabulary
        for a server that publishes nothing should not be overruled by a probe that returned
        nothing.
        """
        cache_key = (kind, _key(base_url, model_id))
        found: Thinking | None = None
        now = time.monotonic()
        entry = cls._cache.get(cache_key)
        if entry is not None and now - entry[0] < DEFAULT_TTL:
            found = entry[1]
        else:
            async with cls._guard():
                # Re-checked inside the lock: a second request that queued behind the first should
                # use its answer rather than ask the same servers again.
                now = time.monotonic()
                entry = cls._cache.get(cache_key)
                if entry is not None and now - entry[0] < DEFAULT_TTL:
                    found = entry[1]
                else:
                    found = await _probe(kind, base_url, model_id, api_key, client)
                    cls._cache[cache_key] = (time.monotonic(), found)
        return found if found.known else declared


def _key(base_url: str, model_id: str) -> str:
    return f"{base_url}|{model_id}"


async def _probe(
    kind: str, base_url: str, model_id: str, api_key: str, client: httpx.AsyncClient | None
) -> Thinking:
    """Ask whichever servers this endpoint might be, in the order that settles it soonest.

    Every probe is individually incapable of raising: a 404, a refused connection, a body that is
    not JSON and a wrong-shaped 200 all mean *this server did not answer*, and the next one is
    tried. A probe that somehow raises anyway is treated as silence, because the alternative is
    a settings screen that will not open.
    """
    if kind == "openrouter":
        return await _first(
            client,
            lambda http: http.get(OPENROUTER_MODELS),
            lambda body: openrouter_thinking(body, model_id),
        )

    # `/props` is llama.cpp's, and is asked of everything: it 404s in a millisecond anywhere else,
    # and gating it on `kind == "llamacpp"` would miss a llama.cpp registered as `openai`, which
    # is the ordinary way somebody registers one.
    caps = await EndpointCapabilities.load(base_url, client=client)
    if caps.thinking_toggle:
        return Thinking(toggle=True, source="llamacpp")

    root = props_url(base_url)

    found = await _first(
        client,
        lambda http: http.get(f"{root}/model_group/info", headers=_auth(api_key)),
        lambda body: litellm_thinking(body, model_id),
        keep=lambda t: t.source == "litellm",
    )
    if found.known:
        return found

    if kind == "ollama":
        return await _first(
            client,
            lambda http: http.post(f"{root}/api/show", json={"model": model_id}),
            ollama_thinking,
            keep=lambda t: t.source == "ollama",
        )

    if kind == "google":
        return await _first(
            client,
            lambda http: http.get(
                GEMINI_MODELS.format(root=root, model=model_id),
                headers=_gemini_auth(api_key),
            ),
            gemini_thinking,
            keep=lambda t: t.source == "gemini",
        )

    return NOTHING


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _gemini_auth(api_key: str) -> dict[str, str]:
    return {"x-goog-api-key": api_key} if api_key else {}


async def _first(
    client: httpx.AsyncClient | None,
    send: Callable[[httpx.AsyncClient], Awaitable[httpx.Response]],
    read: Callable[[object], Thinking],
    keep: Callable[[Thinking], bool] | None = None,
) -> Thinking:
    """One request, one reading of it, and silence on anything unexpected."""
    try:
        owns = client is None
        http = client or httpx.AsyncClient(timeout=5.0)
        try:
            answer = await send(http)
            if answer.status_code != 200:
                return NOTHING
            found = read(answer.json())
        finally:
            if owns:
                await http.aclose()
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return NOTHING
    # `keep` distinguishes "this server answered and says no" from "this is not that server",
    # which matters for Ollama and LiteLLM: both return 200 with a body for a model they do not
    # have, and treating that as an answer would report a negative the other server contradicts.
    if keep is not None and not keep(found):
        return NOTHING
    return found

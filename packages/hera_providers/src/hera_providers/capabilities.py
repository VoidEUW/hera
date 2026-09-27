"""What a local endpoint says about the model it is serving.

A self-hosted server is not obliged to publish anything about itself, but llama.cpp does, at
``/props``, and two of the answers matter here:

- ``chat_template_caps`` declares which template features the loaded model understands. For
  MiniCPM5-2B it says ``"supports_reasoning_effort": false`` -- so a ``reasoning_effort`` sent to
  it is not a setting that is wrong, it is a field the server throws away.
- ``chat_template`` is the Jinja source itself, and whether it *mentions* ``enable_thinking`` is
  the answer to whether the knob that model actually has can be offered.

Both were checked against a real server and they agree: MiniCPM5's template references
``enable_thinking`` three times and never mentions ``reasoning_effort``, which is precisely what
its capability flag claims. Two independent signals from the same server, so the second can stand
in when the first is absent.

**Asked, not matched.** Nothing here inspects a model id to decide what a model is, for the reason
ADR 18 gives: an id is a string somebody typed and guessing wrong means sending a field to a server
that rejects the request. This asks the server that will enforce it.

**Absent means absent.** An endpoint with no ``/props`` -- vLLM, LM Studio, a proxy, anything not
built from llama.cpp -- answers 404 and both flags are ``False``. That is not a failure to be
worked around: it means the endpoint has not said, and a control is not drawn from a silence.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import ClassVar, NamedTuple

import httpx

#: How long a set of endpoint capabilities is good for. Capabilities are a property of the model
#: a server has loaded, which changes when somebody restarts it, so this is generous rather than
#: tight -- and a restart that changes the answer is not worth a request per page load to catch.
TTL_SECONDS = 3600.0

#: The template kwarg the reasoning-model convention uses. Not a Hera concept: it is the name
#: templates across Qwen, GLM, DeepSeek and MiniCPM already read, and the only reason this package
#: knows it is that deciding whether to *offer* it means knowing whether it would do anything.
THINKING_KWARG = "enable_thinking"

#: Path suffixes that sit in front of the routes rather than being part of the server's root.
#: ``/props`` is served by llama.cpp at the root, so an OpenAI-compatible ``base_url`` of
#: ``http://host:8080/v1`` has to lose the ``/v1`` before it can be asked anything.
_API_SUFFIXES = ("/v1", "/api/v1", "/openai/v1")


class Capabilities(NamedTuple):
    """What one endpoint says about the model it is serving."""

    supports_reasoning_effort: bool = False
    """Whether a ``reasoning_effort`` would be honoured. False means *ignored*, not *rejected*:
    llama.cpp accepts an unknown top-level field and carries on, so the cost of guessing wrong is
    a setting that silently does nothing."""

    thinking_toggle: bool = False
    """Whether ``chat_template_kwargs.enable_thinking`` would reach the template. Offered as an
    on/off control, because that is the shape every model declaring it actually wants -- a
    boolean, not a vocabulary."""


NOTHING = Capabilities()


def props_url(base_url: str) -> str:
    """Where to ask an endpoint about itself.

    Strips the OpenAI-compatible suffix, because ``/props`` hangs off the server's root and a
    ``base_url`` of ``http://host:8080/v1`` is a routes prefix rather than a prefix of the server.
    Anything else is left exactly as registered -- an endpoint on a path prefix is unusual, and
    guessing at it would be the thing this module exists to avoid.
    """
    trimmed = base_url.rstrip("/")
    for suffix in _API_SUFFIXES:
        if trimmed.endswith(suffix):
            return trimmed[: -len(suffix)]
    return trimmed


def _cap_flag(props: object, name: str) -> bool | None:
    """One boolean out of ``chat_template_caps``, or ``None`` if it is not declared."""
    caps = props.get("chat_template_caps") if isinstance(props, dict) else None
    if not isinstance(caps, dict):
        return None
    value = caps.get(name)
    return value if isinstance(value, bool) else None


def template_capabilities(props: object) -> Capabilities:
    """Read what an endpoint published about the model it is serving.

    Both answers are ``False`` by default and only ever set from something the server said. The
    template is inspected for :data:`THINKING_KWARG` by name and nothing more: a template that
    mentions it reads it, and a template that does not would ignore it, so a substring test is
    the whole of the question. It is not a Jinja parser and does not pretend to be one -- it
    answers *would this do anything*, which is the only thing being decided.
    """
    if not isinstance(props, dict):
        return NOTHING

    # The server's own capability object is the answer when it declares one. Where it does not,
    # the template is asked instead: a template that *reads* `reasoning_effort` is one that
    # honours it. Same question, same evidence, asked in the other direction.
    declared = _cap_flag(props, "supports_reasoning_effort")
    effort = declared if declared is not None else _mentions(props, "reasoning_effort")

    return Capabilities(
        supports_reasoning_effort=effort,
        thinking_toggle=_mentions(props, THINKING_KWARG),
    )


def _mentions(props: object, name: str) -> bool:
    """Whether the published chat template refers to ``name`` at all.

    A whole-word match on purpose. ``enable_thinking`` and ``reasoning_effort`` are long enough
    that a substring test would not confuse them with each other, but a template that merely
    *mentions* ``supports_reasoning_effort`` in a comment should not be read as honouring the
    field, and ``some_other_reasoning_effort`` is a different name.
    """
    template = props.get("chat_template") if isinstance(props, dict) else None
    if not isinstance(template, str) or not template:
        return False
    return re.search(rf"\b{re.escape(name)}\b", template) is not None


class EndpointCapabilities:
    """What each endpoint has said, remembered per ``base_url``.

    Process-wide and cached, for the same reason the OpenRouter catalogue is: there is one answer
    per endpoint, every request wants the same one, and two requests arriving together would
    otherwise both ask. A failure is cached too, so an endpoint that is down is not asked again on
    every keystroke.
    """

    _cache: ClassVar[dict[str, tuple[float, Capabilities]]] = {}
    _lock: asyncio.Lock | None = None

    @classmethod
    def _guard(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def forget(cls) -> None:
        """Drop everything remembered. For tests, and for a person who has just restarted a
        server underneath a model registration that has not changed."""
        cls._cache.clear()

    @classmethod
    def peek(cls, base_url: str) -> Capabilities:
        """What is already known about an endpoint, without asking it anything."""
        entry = cls._cache.get(base_url)
        return entry[1] if entry is not None else NOTHING

    @classmethod
    async def load(cls, base_url: str, *, client: httpx.AsyncClient | None = None) -> Capabilities:
        """What an endpoint says, asking it at most once per :data:`TTL_SECONDS`.

        Never raises. A 404, a refused connection and a body that is not JSON all mean the same
        thing -- this endpoint has not told us anything -- and all of them are cached so the
        question is not asked again.
        """
        now = time.monotonic()
        entry = cls._cache.get(base_url)
        if entry is not None and now - entry[0] < TTL_SECONDS:
            return entry[1]

        async with cls._guard():
            now = time.monotonic()
            entry = cls._cache.get(base_url)
            if entry is not None and now - entry[0] < TTL_SECONDS:
                return entry[1]
            found = await _ask(base_url, client)
            cls._cache[base_url] = (time.monotonic(), found)
            return found


async def _ask(base_url: str, client: httpx.AsyncClient | None) -> Capabilities:
    url = f"{props_url(base_url)}/props"
    try:
        owns = client is None
        http = client or httpx.AsyncClient(timeout=5.0)
        try:
            answer = await http.get(url)
            if answer.status_code != 200:
                return NOTHING
            return template_capabilities(answer.json())
        finally:
            if owns:
                await http.aclose()
    except (httpx.HTTPError, ValueError):
        return NOTHING

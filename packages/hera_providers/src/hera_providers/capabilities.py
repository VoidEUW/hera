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
from collections.abc import Sequence
from typing import ClassVar, Literal, NamedTuple

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

#: How a tool call is expected to arrive. ``native`` means the inference engine's tool parser
#: recognises the model's wire format and re-exposes it as OpenAI-shaped ``tool_calls``, which is
#: every mainstream engine against every mainstream model. ``textual`` means the model writes the
#: call into its own prose -- ``<tool_call>{...}</tool_call>`` and its relatives -- and
#: nothing is lifting it out, so a call arrives as an assistant message rather than as a call.
#: ``unknown`` means the endpoint did not say, which is the ordinary case.
#:
#: This is a *reporting* shape and not a switch. Detection tells a person what their endpoint can
#: do; it never changes what is sent, because silently reformatting a model's calls would be the
#: ADR 18 failure with extra steps.
ToolCallShape = Literal["native", "textual", "unknown"]

#: The honest answer for an endpoint that published nothing.
UNKNOWN: ToolCallShape = "unknown"

#: The dialect markers a chat template or a server's answer has to mention for a call to be
#: possible at all. Matched as whole words inside the Jinja source, the same way
#: :data:`THINKING_KWARG` is, and for the same reason: the question is *would this do anything*,
#: which is not a Jinja parse.
_TOOL_MARKERS = ("tools", "tool_calls", "render_tools")

#: A Jinja comment, ``{# ... #}``, matched with DOTALL because they wrap. Replaced with a space
#: rather than removed so that two words either side of a comment do not become one word.
_JINJA_COMMENT = re.compile(r"{#.*?#}", re.DOTALL)


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

    tool_call_shape: ToolCallShape = UNKNOWN
    """How this endpoint can be expected to deliver a tool call, and the reason it is allowed to
    say so. ``unknown`` is the default and is not a failure to be worked around -- it is the
    honest answer for an endpoint that published nothing, which is most of them, and a control is
    never drawn from a silence."""


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
        tool_call_shape=tool_call_shape(props),
    )


def tool_call_shape(props: object) -> ToolCallShape:
    """How this endpoint says it will deliver a tool call, or ``unknown`` if it does not say.

    The question has two halves and only the second is answerable from ``/props``:

    * **Can the template render tools at all?** A template with no tools path -- no ``tools`` in
      its loop, no ``render_tools`` call -- cannot put a declaration in front of the model, so a
      call is not something it has been taught to make. That is the same evidence
      :data:`THINKING_KWARG` is read from, asked about a different word.
    * **Will something lift the call out afterwards?** That is the engine's tool parser, not the
      model, and no engine publishes it over ``/props``. So the honest answer here is almost always
      ``native`` -- which is the truth for vLLM, SGLang, llama.cpp and Ollama against every model
      they ship a parser for -- rather than a guess that the wrong answer quietly degrades.

    ``textual`` is therefore *not* inferred here. It is what a caller reports after watching a turn
    arrive with the call written into the prose, which is the only place that can actually see it.
    Deciding it from a template would mean claiming a model cannot call tools properly on the
    strength of a substring, and the failure that follows -- she stops calling tools and nothing
    says why -- is the thing ADR 18 exists to prevent.
    """
    if not isinstance(props, dict):
        return UNKNOWN
    if _cap_flag(props, "supports_tool_calls") is False:
        # The server said no, which is a real answer and the only one that can move the shape off
        # `unknown` from here.
        return "textual"
    return "native" if _mentions_any(props, _TOOL_MARKERS) else UNKNOWN


def _mentions_any(props: object, names: Sequence[str]) -> bool:
    return any(_mentions(props, name) for name in names)


def _mentions(props: object, name: str) -> bool:
    """Whether the published chat template refers to ``name`` as code.

    Two things are excluded, and the first is the one that is easy to miss:

    * **Comments.** Jinja's ``{# ... #}`` is stripped first. A template's header routinely explains
      what it does -- "tools are rendered by ``render_tools`` upstream" -- and a template that
      *describes* a tools path has no tools path. Without this a well-documented template reports a
      capability it does not have, which is worse than reporting none: the control goes up and does
      nothing. The reasoning fields happened to be protected by the rule below, because
      ``supports_reasoning_effort`` cannot match ``\\breasoning_effort\\b`` (an underscore is a word
      character, so there is no boundary before it) -- but ``tools`` on its own in a comment is a
      plain match, and nothing else would have caught it.
    * **Longer names containing the field.** A whole-word match, so ``my_reasoning_effort_setting``
      is a different name.

    Neither is a Jinja parse. The question is *would this do anything*, which is all that is being
    decided.
    """
    template = props.get("chat_template") if isinstance(props, dict) else None
    if not isinstance(template, str) or not template:
        return False
    code = _JINJA_COMMENT.sub(" ", template)
    return re.search(rf"\b{re.escape(name)}\b", code) is not None


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

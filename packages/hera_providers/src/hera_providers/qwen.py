"""The Qwen adapter: stream chunks in, event union out.

Everything provider-specific about the target model is here and nowhere else. It does three
jobs, and the first two are the reason the file exists:

* **Reasoning.** A model served through an OpenAI-compatible endpoint reports its reasoning in
  one of several places, because there is no standard for it and every server picked its own.
  All of them are lifted into :class:`ThinkingDelta`, so no layer above ever sees a tag or
  learns which server it was talking to -- see :func:`_reasoning_of` for the field shapes and
  why the order they are tried in matters. A thought that turns out to be whitespace only --
  another model family's empty ``<think>\n\n</think>`` -- is swallowed rather than announced;
  see :meth:`QwenAdapter._think`.
* **Tool calls.** They arrive as fragments indexed by position, with the arguments streamed as
  partial JSON. They are accumulated here and emitted whole -- preceded by one
  :class:`ToolCallStarted` as soon as the *name* is known, because the whole call can be
  minutes away and a person watching an empty screen cannot tell working from stopped.
* **Finish.** One :class:`TurnEnd` at the end, always, with the reason normalised.

This class is pure: no I/O, no httpx, nothing async. That is what makes the awkward part --
a ``<think>`` tag split across two chunks -- cheap to test exhaustively.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from hera_providers.events import (
    Event,
    FinishReason,
    TextDelta,
    ThinkingDelta,
    ToolCallReady,
    ToolCallStarted,
    TurnEnd,
    Usage,
)

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"

_FINISH_REASONS: dict[str, FinishReason] = {
    "stop": "stop",
    "length": "length",
    "max_tokens": "length",
    "tool_calls": "tool_calls",
    "function_call": "tool_calls",
}


class QwenAdapter:
    """One instance per stream. Not reusable, and not thread-safe -- neither is a stream."""

    def __init__(self) -> None:
        self._splitter = _ThinkSplitter()
        self._calls: dict[int, _PartialCall] = {}
        self._reason: FinishReason | None = None
        self._usage: Usage | None = None
        self._finished = False
        self._think_buffer = ""
        self._think_has_content = False

    def feed(self, chunk: Mapping[str, Any]) -> Iterator[Event]:
        """Consume one decoded chunk of the stream."""
        usage = chunk.get("usage")
        if isinstance(usage, Mapping):
            self._usage = Usage.model_validate(dict(usage))

        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            # A trailing usage-only chunk has an empty `choices`; that is not an error.
            return

        choice = choices[0]
        delta = choice.get("delta") or {}

        reasoning = _reasoning_of(delta)
        if reasoning:
            yield from self._think(reasoning)

        content = delta.get("content")
        if isinstance(content, str) and content:
            yield from self._route(_as_events(self._splitter.feed(content)))

        for raw in delta.get("tool_calls") or []:
            yield from self._accumulate(raw)

        finish = choice.get("finish_reason")
        if isinstance(finish, str) and finish:
            self._reason = _FINISH_REASONS.get(finish, "stop")

    def _think(self, text: str) -> Iterator[Event]:
        """Gate a run of reasoning text so a whitespace-only think block is silent.

        A Gemma-family template can emit a well-formed but empty ``<think>\\n\\n</think>``,
        which is a *present* thought with nothing in it -- the browser has no way to tell that
        apart from a real one and shows "thought · 0 words". Buffering until non-whitespace
        text is seen lets that case simply never announce a thought at all; a stream that turns
        out to have real reasoning still streams it live from then on.
        """
        if self._think_has_content:
            yield ThinkingDelta(text=text)
            return
        self._think_buffer += text
        if self._think_buffer.strip():
            self._think_has_content = True
            yield ThinkingDelta(text=self._think_buffer)
            self._think_buffer = ""

    def _route(self, events: Iterable[Event]) -> Iterator[Event]:
        """Send split-out thinking runs through the gate; text runs pass straight through."""
        for event in events:
            if isinstance(event, ThinkingDelta):
                yield from self._think(event.text)
            else:
                yield event

    def finish(self) -> Iterator[Event]:
        """Flush and close. Calling it twice yields nothing the second time."""
        if self._finished:
            return
        self._finished = True

        yield from self._route(_as_events(self._splitter.flush()))
        for index in sorted(self._calls):
            yield self._calls[index].build()

        reason = self._reason or "stop"
        if self._calls:
            # Some servers report `stop` alongside tool calls. The union promises that a turn
            # ending in calls says so, because that is what decides whether the loop runs again.
            reason = "tool_calls"
        yield TurnEnd(reason=reason, usage=self._usage)

    def _accumulate(self, raw: object) -> Iterator[Event]:
        """Fold one fragment into the call it belongs to, announcing the call once.

        The announcement is deliberately at the *end*: ``id`` and ``function.name`` arrive in
        the same fragment, and reading the whole of it before saying anything is what makes the
        announced id the one :meth:`_PartialCall.build` will use. Saying it earlier would risk
        naming a call ``call_0`` and then dispatching it as something else, which is worse than
        saying nothing.
        """
        if not isinstance(raw, Mapping):
            return
        index = raw.get("index")
        index = index if isinstance(index, int) else 0
        call = self._calls.setdefault(index, _PartialCall(index=index))

        identifier = raw.get("id")
        if isinstance(identifier, str) and identifier:
            call.id = identifier

        function = raw.get("function")
        if not isinstance(function, Mapping):
            return
        name = function.get("name")
        if isinstance(name, str) and name:
            # Appended, not assigned: a few servers split even the name across chunks.
            call.name += name
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            call.arguments += arguments

        if call.name and not call.announced:
            # Once per call, and only once there is a name to announce -- a row that says
            # "she is calling something" is worth no more than the running indicator already
            # on screen. Arguments are not looked at: half a JSON object is not a name.
            call.announced = True
            yield ToolCallStarted(id=call.call_id, name=call.name)


@dataclass
class _PartialCall:
    """A tool call being assembled out of stream fragments."""

    index: int
    id: str = ""
    name: str = ""
    arguments: str = ""
    announced: bool = False
    """Whether a :class:`ToolCallStarted` has already gone out for this call. A call arrives in
    many fragments and is announced on the first one that names it."""

    @property
    def call_id(self) -> str:
        """The identity this call will be dispatched under.

        One expression, read by both the announcement and the finished call, so the two cannot
        drift apart and leave the browser with a row it can never pair up. The fallback exists
        because a few servers omit ``id`` entirely on a single-call turn.
        """
        return self.id or f"call_{self.index}"

    def build(self) -> ToolCallReady:
        call_id = self.call_id
        raw = self.arguments
        if not raw.strip():
            # A tool that takes no arguments; servers send "", "{}" or nothing at all.
            return ToolCallReady(id=call_id, name=self.name, arguments={}, raw_arguments=raw)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return ToolCallReady(
                id=call_id, name=self.name, raw_arguments=raw, parse_error=str(exc)
            )
        if not isinstance(parsed, dict):
            return ToolCallReady(
                id=call_id,
                name=self.name,
                raw_arguments=raw,
                parse_error=f"arguments are {type(parsed).__name__}, expected a JSON object",
            )
        return ToolCallReady(id=call_id, name=self.name, arguments=parsed, raw_arguments=raw)


@dataclass
class _ThinkSplitter:
    """Separates ``<think>...</think>`` out of a content stream that arrives in fragments.

    The whole difficulty is that a tag can be split across chunk boundaries: ``"...<thi"`` then
    ``"nk>..."``. So text is only released once it is certain not to be the start of a tag --
    any suffix that could still grow into one is held back until the next chunk decides.

    The cost is a known and accepted one: a model that writes the literal string ``<think>``
    in its prose has that treated as a tag. Nothing else can tell the two apart in a stream.
    """

    buffer: str = field(default="")
    inside: bool = field(default=False)

    def feed(self, text: str) -> list[tuple[bool, str]]:
        """Return ``(is_thinking, text)`` runs that are now certain."""
        self.buffer += text
        runs: list[tuple[bool, str]] = []
        while True:
            tag = THINK_CLOSE if self.inside else THINK_OPEN
            index = self.buffer.find(tag)
            if index >= 0:
                if index:
                    runs.append((self.inside, self.buffer[:index]))
                self.buffer = self.buffer[index + len(tag) :]
                self.inside = not self.inside
                continue

            held = _partial_tag_suffix(self.buffer, tag)
            release = len(self.buffer) - held
            if release:
                runs.append((self.inside, self.buffer[:release]))
            self.buffer = self.buffer[release:]
            return runs

    def flush(self) -> list[tuple[bool, str]]:
        """Release whatever is still held. A half-written tag comes out as the text it is."""
        rest, self.buffer = self.buffer, ""
        return [(self.inside, rest)] if rest else []


def _partial_tag_suffix(buffer: str, tag: str) -> int:
    """Length of the longest suffix of ``buffer`` that could still grow into ``tag``."""
    for size in range(min(len(buffer), len(tag) - 1), 0, -1):
        if tag.startswith(buffer[-size:]):
            return size
    return 0


def _as_events(runs: list[tuple[bool, str]]) -> Iterator[Event]:
    for thinking, text in runs:
        yield ThinkingDelta(text=text) if thinking else TextDelta(text=text)


def _reasoning_of(delta: Mapping[str, Any]) -> str:
    """The reasoning in one delta, whichever field this server decided to put it in.

    There is no standard here, and reading only one spelling is not a cosmetic bug: a reasoning
    model whose thoughts land in a field nothing reads streams *nothing at all* until it reaches
    ``content``, because a delta carrying only reasoning has an empty ``content``. The turn looks
    frozen for as long as the model thinks -- which is worst exactly when the question was
    hardest. That was the observed failure on OpenRouter, where a local LM Studio serving the
    same weights was fine.

    Three spellings, tried in this order, and **the first one holding something legible wins**
    rather than all of them being concatenated -- a server that sends both ``reasoning`` and
    ``reasoning_details`` (OpenRouter does, the first for backwards compatibility) would
    otherwise show every thought twice.

    *Legible* rather than merely present, because :meth:`QwenAdapter._think` swallows a
    whitespace-only thought: selecting a blank ``reasoning_content`` over a filled ``reasoning``
    beside it would drop that delta's reasoning entirely rather than fall through to it. When
    **nothing** is legible the first field that was there at all is returned anyway, whitespace
    and all -- ``_think`` holds it against the next chunk, and that is what keeps a thought
    opening with a newline from arriving with its first line missing. Either way the value is
    returned unstripped: the whitespace belongs to the thought, and the gate decides what is
    worth announcing.

    * ``reasoning_content`` -- a plain string beside ``content``. LM Studio, vLLM, llama.cpp,
      and DeepSeek's own API. The original spelling and still the commonest.
    * ``reasoning_details`` -- OpenRouter's structured form, a list of blocks. Preferred over
      ``reasoning`` below because it is the documented current shape, and it is read leniently:
      an ``encrypted`` block carries opaque ``data`` rather than ``text`` and is skipped, which
      is why this can be present and still yield nothing.
    * ``reasoning`` -- a plain string. OpenRouter's compatibility field, and the fallback for
      when the structured form held nothing legible.
    """
    found: list[str] = []
    direct = delta.get("reasoning_content")
    if isinstance(direct, str) and direct:
        found.append(direct)
    detailed = _detailed_reasoning(delta.get("reasoning_details"))
    if detailed:
        found.append(detailed)
    plain = delta.get("reasoning")
    if isinstance(plain, str) and plain:
        found.append(plain)

    for value in found:
        if value.strip():
            return value
    # Nothing legible anywhere, so the whitespace itself is the best answer available: `_think`
    # holds it against the next chunk rather than dropping it, which is what keeps a thought
    # that opens with a newline from arriving with its first line missing.
    return found[0] if found else ""


def _detailed_reasoning(details: object) -> str:
    """The legible text of a ``reasoning_details`` list, or ``""``.

    Deliberately lenient about the block type: what matters is whether a block carries something
    a person can read, not what it calls itself. ``text`` and ``summary`` are the two fields that
    do; an encrypted block has neither and contributes nothing, rather than putting a wall of
    base64 where a thought should be.
    """
    if not isinstance(details, list):
        return ""
    found: list[str] = []
    for block in details:
        if not isinstance(block, Mapping):
            continue
        for key in ("text", "summary"):
            value = block.get(key)
            if isinstance(value, str) and value:
                found.append(value)
                break
    return "".join(found)

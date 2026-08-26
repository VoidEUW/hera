"""The Qwen adapter: stream chunks in, event union out.

Everything provider-specific about the target model is here and nowhere else. It does three
jobs, and the first two are the reason the file exists:

* **Reasoning.** Qwen served through an OpenAI-compatible endpoint reports its reasoning
  either in a ``reasoning_content`` field beside ``content``, or -- depending on the server
  and its chat template -- inline in ``content`` wrapped in ``<think>`` tags. Both are lifted
  into :class:`ThinkingDelta`, so no layer above ever sees a tag.
* **Tool calls.** They arrive as fragments indexed by position, with the arguments streamed as
  partial JSON. They are accumulated here and emitted whole.
* **Finish.** One :class:`TurnEnd` at the end, always, with the reason normalised.

This class is pure: no I/O, no httpx, nothing async. That is what makes the awkward part --
a ``<think>`` tag split across two chunks -- cheap to test exhaustively.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from hera_providers.events import (
    Event,
    FinishReason,
    TextDelta,
    ThinkingDelta,
    ToolCallReady,
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

        reasoning = delta.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning:
            yield ThinkingDelta(text=reasoning)

        content = delta.get("content")
        if isinstance(content, str) and content:
            yield from _as_events(self._splitter.feed(content))

        for raw in delta.get("tool_calls") or []:
            self._accumulate(raw)

        finish = choice.get("finish_reason")
        if isinstance(finish, str) and finish:
            self._reason = _FINISH_REASONS.get(finish, "stop")

    def finish(self) -> Iterator[Event]:
        """Flush and close. Calling it twice yields nothing the second time."""
        if self._finished:
            return
        self._finished = True

        yield from _as_events(self._splitter.flush())
        for index in sorted(self._calls):
            yield self._calls[index].build()

        reason = self._reason or "stop"
        if self._calls:
            # Some servers report `stop` alongside tool calls. The union promises that a turn
            # ending in calls says so, because that is what decides whether the loop runs again.
            reason = "tool_calls"
        yield TurnEnd(reason=reason, usage=self._usage)

    def _accumulate(self, raw: object) -> None:
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


@dataclass
class _PartialCall:
    """A tool call being assembled out of stream fragments."""

    index: int
    id: str = ""
    name: str = ""
    arguments: str = ""

    def build(self) -> ToolCallReady:
        call_id = self.id or f"call_{self.index}"
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

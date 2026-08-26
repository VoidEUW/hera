"""What comes back from a tool call, in one shape whatever happened.

A tool that fails is not an exception here. Denied by policy, no such tool, server not
running, took too long, or the tool itself reported an error -- all of them arrive as a
:class:`ToolResult` with ``ok`` false and a ``text`` written to be read *by the model*, which
can then apologise, try a different tool, or ask. That is the same reasoning as
``ToolCallReady.parse_error`` in ``hera_providers``: one bad call must not end the turn.

``blocks`` keeps the protocol's content list as plain JSON. ADR 4 warned that tool results are
text and structured content and that renderers must handle both; flattening to a string at
this boundary would be the point where an image result becomes unrecoverable.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from mcp.types import CallToolResult, ContentBlock, TextContent
from pydantic import BaseModel, ConfigDict, Field


class Failure(StrEnum):
    """Why a call did not produce a normal result.

    Worth distinguishing because each one renders differently and suggests a different remedy:
    ``DENIED`` is a decision someone made, ``UNAVAILABLE`` is a server to start, ``TOOL_ERROR``
    is the tool working exactly as designed and saying no.
    """

    DENIED = "denied"
    UNKNOWN_TOOL = "unknown_tool"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    TOOL_ERROR = "tool_error"


class ToolInvocation(BaseModel):
    """One call, on its way in.

    Deliberately not ``hera_providers.ToolCallReady``: this package does not import that one,
    and the two are not the same thing anyway -- a call can also come from the interface (a
    retry, a confirmation) rather than from a model. The turn maps between them.
    """

    model_config = ConfigDict(frozen=True)

    call_id: str
    tool: str
    """The qualified ``server__tool`` name."""

    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """The outcome of one tool call."""

    model_config = ConfigDict(frozen=True)

    call_id: str
    """The id of the call this answers. It has to travel back to the model unchanged, or the
    result is matched to nothing and silently ignored."""

    tool: str
    """The qualified name that was called, including one the catalogue does not have."""

    ok: bool = True
    failure: Failure | None = None

    text: str = ""
    """The result as the model should read it -- flattened content, or the failure explained.

    Always populated, including on failure, because this is what becomes the ``TOOL`` message
    of the next request. An empty string there is a wasted round-trip.
    """

    structured: Any = None
    """``structured_content`` from the protocol, when the tool returned any."""

    blocks: tuple[dict[str, Any], ...] = ()
    """The content blocks as JSON, for rendering. Text, images, resource links."""

    duration_ms: int = 0

    @classmethod
    def from_call(
        cls,
        *,
        call_id: str,
        tool: str,
        result: CallToolResult,
        duration_ms: int = 0,
    ) -> ToolResult:
        """Convert a protocol result, honouring its own ``is_error`` flag."""
        text = flatten(result.content)
        return cls(
            call_id=call_id,
            tool=tool,
            ok=not result.is_error,
            failure=Failure.TOOL_ERROR if result.is_error else None,
            text=text or ("the tool reported an error" if result.is_error else ""),
            structured=result.structured_content,
            blocks=tuple(
                # Aliased and without the nulls: these are persisted with the event stream and
                # sent to the browser, so they should look like the protocol's own JSON rather
                # than like a pydantic dump of it.
                block.model_dump(mode="json", by_alias=True, exclude_none=True)
                for block in result.content
            ),
            duration_ms=duration_ms,
        )

    @classmethod
    def failed(
        cls,
        *,
        call_id: str,
        tool: str,
        failure: Failure,
        text: str,
        duration_ms: int = 0,
    ) -> ToolResult:
        """A call that never reached a tool, or reached one that could not answer."""
        return cls(
            call_id=call_id,
            tool=tool,
            ok=False,
            failure=failure,
            text=text,
            duration_ms=duration_ms,
        )


def flatten(blocks: Sequence[ContentBlock]) -> str:
    """Render content blocks as the plain text that goes back to the model.

    Anything that is not text becomes a short placeholder rather than being dropped: a model
    told ``[image image/png]`` knows the call worked and produced a picture, where silence
    reads as a tool that returned nothing.
    """
    lines = [
        block.text if isinstance(block, TextContent) else _placeholder(block) for block in blocks
    ]
    return "\n".join(line for line in lines if line)


def _placeholder(block: ContentBlock) -> str:
    detail = getattr(block, "mime_type", None) or getattr(block, "uri", None)
    return f"[{block.type} {detail}]" if detail else f"[{block.type}]"

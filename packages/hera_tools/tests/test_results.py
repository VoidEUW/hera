"""Turning a protocol result into the one shape everything above this package reads."""

from __future__ import annotations

from hera_tools.results import Failure, ToolResult, flatten
from mcp.types import CallToolResult, ContentBlock, ImageContent, ResourceLink, TextContent


def _text(text: str) -> TextContent:
    return TextContent(type="text", text=text)


def test_text_content_is_joined() -> None:
    assert flatten([_text("one"), _text("two")]) == "one\ntwo"


def test_other_content_becomes_a_placeholder() -> None:
    """Dropping it would read to the model as a tool that returned nothing at all."""
    blocks: list[ContentBlock] = [
        ImageContent(type="image", data="AA==", mimeType="image/png"),
        ResourceLink(type="resource_link", name="notes", uri="file:///notes.md"),
    ]
    assert flatten(blocks) == "[image image/png]\n[resource_link file:///notes.md]"


def test_a_successful_call() -> None:
    result = ToolResult.from_call(
        call_id="c1",
        tool="fs__read",
        result=CallToolResult(content=[_text("hello")]),
        duration_ms=12,
    )
    assert result.ok
    assert result.failure is None
    assert result.text == "hello"
    assert result.duration_ms == 12


def test_structured_content_survives() -> None:
    result = ToolResult.from_call(
        call_id="c1",
        tool="fs__stat",
        result=CallToolResult(content=[_text("{}")], structuredContent={"size": 12}),
    )
    assert result.structured == {"size": 12}


def test_blocks_are_kept_as_json_for_rendering() -> None:
    """ADR 4: results are text *and* structured content, and renderers handle both."""
    result = ToolResult.from_call(
        call_id="c1",
        tool="fs__read",
        result=CallToolResult(content=[ImageContent(type="image", data="AA==", mimeType="i/png")]),
    )
    assert result.blocks == ({"type": "image", "data": "AA==", "mimeType": "i/png"},)


def test_a_tool_that_reports_an_error_is_not_an_exception() -> None:
    result = ToolResult.from_call(
        call_id="c1",
        tool="fs__read",
        result=CallToolResult(content=[_text("no such file")], isError=True),
    )
    assert not result.ok
    assert result.failure is Failure.TOOL_ERROR
    assert result.text == "no such file"


def test_an_error_without_text_still_says_something() -> None:
    """Whatever happens, the model gets a sentence back -- silence wastes the round trip."""
    result = ToolResult.from_call(
        call_id="c1", tool="fs__read", result=CallToolResult(content=[], isError=True)
    )
    assert result.text == "the tool reported an error"


def test_a_failure_that_never_reached_a_tool() -> None:
    result = ToolResult.failed(
        call_id="c1", tool="fs__read", failure=Failure.TIMEOUT, text="too slow"
    )
    assert not result.ok
    assert result.failure is Failure.TIMEOUT
    assert result.text == "too slow"

"""The persisted union: what survives a save, and what gets merged on the way in."""

from __future__ import annotations

from hera_chats import (
    CHAT_EVENT_ADAPTER,
    LIST_ADAPTER,
    ChatEvent,
    PermissionDecided,
    PermissionRequired,
    SkillSelected,
    ToolResultEvent,
    TurnClosed,
    coalesce,
    visible_text,
)
from hera_providers import TextDelta, ThinkingDelta, ToolCallReady, Usage

EVERY_VARIANT: list[ChatEvent] = [
    SkillSelected(skill="tdd", reason="pinned"),
    ThinkingDelta(text="hmm"),
    TextDelta(text="Because "),
    ToolCallReady(id="c1", name="fs__read_file", arguments={"path": "x"}),
    PermissionRequired(call_id="c1", tool="fs__read_file", reason="it writes to disk"),
    PermissionDecided(call_id="c1", allowed=True, remembered=True),
    ToolResultEvent(call_id="c1", tool="fs__read_file", text="contents", duration_ms=12),
    TurnClosed(reason="completed", usage=Usage(total_tokens=90), iterations=2),
]


class TestTheUnion:
    def test_every_variant_round_trips_through_the_adapter(self) -> None:
        """Persistence goes through the union rather than through each variant, so surviving
        a save stays a property of the union itself."""
        for event in EVERY_VARIANT:
            dumped = CHAT_EVENT_ADAPTER.dump_python(event, mode="json")
            assert CHAT_EVENT_ADAPTER.validate_python(dumped) == event

    def test_a_whole_turn_round_trips(self) -> None:
        dumped = LIST_ADAPTER.dump_python(EVERY_VARIANT, mode="json")
        assert LIST_ADAPTER.validate_python(dumped) == EVERY_VARIANT

    def test_the_type_field_is_what_discriminates(self) -> None:
        """The browser keys off this and nothing else. A variant without a stable literal
        would be one the interface has to guess at."""
        dumped = LIST_ADAPTER.dump_python(EVERY_VARIANT, mode="json")
        assert [item["type"] for item in dumped] == [
            "skill_selected",
            "thinking_delta",
            "text_delta",
            "tool_call_ready",
            "permission_required",
            "permission_decided",
            "tool_result",
            "turn_closed",
        ]

    def test_the_provider_variants_cross_unchanged(self) -> None:
        """A text_delta out of hera_providers is a text_delta here -- same literal, no
        conversion, so nothing can drift between the two unions."""
        original = TextDelta(text="hello")
        assert CHAT_EVENT_ADAPTER.validate_python(original.model_dump()) == original

    def test_turn_end_is_not_part_of_this_union(self) -> None:
        """It is the model's full stop for one round trip and a turn has several. The
        orchestrator consumes them so the interface has exactly one terminator."""
        dumped = LIST_ADAPTER.dump_python(EVERY_VARIANT, mode="json")
        assert "turn_end" not in [item["type"] for item in dumped]

    def test_a_tool_result_keeps_its_content_blocks(self) -> None:
        """ADR 4: a result can be an image or a resource link, and flattening to a string
        here is where that becomes unrecoverable."""
        event = ToolResultEvent(
            call_id="c1",
            tool="fs__read",
            blocks=({"type": "image", "mimeType": "image/png", "data": "abc"},),
        )
        restored = CHAT_EVENT_ADAPTER.validate_python(
            CHAT_EVENT_ADAPTER.dump_python(event, mode="json")
        )
        assert isinstance(restored, ToolResultEvent)
        assert restored.blocks[0]["mimeType"] == "image/png"

    def test_an_unrecognised_failure_string_still_validates(self) -> None:
        """A plain string rather than the enum, so a value added upstream reads through to
        the interface as itself instead of failing validation on a stored event."""
        stored = {"type": "tool_result", "call_id": "c", "tool": "t", "failure": "brand_new"}
        restored = CHAT_EVENT_ADAPTER.validate_python(stored)
        assert isinstance(restored, ToolResultEvent)
        assert restored.failure == "brand_new"


class TestCoalescing:
    def test_consecutive_text_becomes_one_event(self) -> None:
        merged = coalesce([TextDelta(text="Hel"), TextDelta(text="lo"), TextDelta(text="!")])
        assert merged == [TextDelta(text="Hello!")]

    def test_thinking_merges_separately_from_text(self) -> None:
        merged = coalesce([ThinkingDelta(text="a"), ThinkingDelta(text="b"), TextDelta(text="c")])
        assert merged == [ThinkingDelta(text="ab"), TextDelta(text="c")]

    def test_anything_between_two_fragments_stops_the_merge(self) -> None:
        """An emotion called mid-sentence has to stay where she put it."""
        call = ToolCallReady(id="c1", name="hera__emotion")
        merged = coalesce([TextDelta(text="a"), call, TextDelta(text="b")])
        assert merged == [TextDelta(text="a"), call, TextDelta(text="b")]

    def test_an_empty_list_stays_empty(self) -> None:
        assert coalesce([]) == []

    def test_the_input_is_not_mutated(self) -> None:
        original = [TextDelta(text="a"), TextDelta(text="b")]
        coalesce(original)
        assert len(original) == 2


class TestVisibleText:
    def test_it_is_the_text_deltas_joined(self) -> None:
        assert visible_text([TextDelta(text="Hel"), TextDelta(text="lo")]) == "Hello"

    def test_thinking_is_left_out(self) -> None:
        """Not the answer. Treating it as one is how a chat log starts quoting her
        deliberations back at her."""
        events: list[ChatEvent] = [ThinkingDelta(text="hmm, maybe"), TextDelta(text="Yes.")]
        assert visible_text(events) == "Yes."

    def test_tool_output_is_left_out(self) -> None:
        events = [ToolResultEvent(call_id="c", tool="t", text="file contents")]
        assert visible_text(events) == ""

"""Stored events becoming the conversation the model is sent again.

The case that matters is a turn with tools in it. Flattening one into a single assistant
message loses the pairing between a call and its answer, and a model that cannot match
``tool_call_id`` ignores the result silently — with the turn carrying on as though the tool had
never run.
"""

from __future__ import annotations

from uuid import UUID

from hera_chats.models import Message

from hera_chats import (
    CHAT_EVENT_ADAPTER,
    ChatRepository,
    MessageRepository,
    SkillSelected,
    ToolResultEvent,
    TurnClosed,
    build_history,
    events_of,
    turn_to_messages,
)
from hera_providers import Role, TextDelta, ThinkingDelta, ToolCallReady


def stored(*events: object) -> Message:
    return Message(
        owner_id=UUID(int=1),
        chat_id=UUID(int=2),
        role="assistant",
        events=[CHAT_EVENT_ADAPTER.dump_python(event, mode="json") for event in events],  # type: ignore[arg-type]
    )


class TestASimpleTurn:
    def test_text_becomes_one_assistant_message(self) -> None:
        wire = turn_to_messages([TextDelta(text="Hello."), TurnClosed()])
        assert [(m.role, m.content) for m in wire] == [(Role.ASSISTANT, "Hello.")]

    def test_thinking_never_comes_back(self) -> None:
        """Replaying it as the answer teaches her that deliberating out loud is what an
        assistant message looks like."""
        wire = turn_to_messages([ThinkingDelta(text="hmm"), TextDelta(text="Yes.")])
        assert [m.content for m in wire] == ["Yes."]

    def test_bookkeeping_events_contribute_nothing_to_the_wire(self) -> None:
        wire = turn_to_messages(
            [SkillSelected(skill="tdd", reason="pinned"), TextDelta(text="Hi."), TurnClosed()]
        )
        assert len(wire) == 1

    def test_an_empty_turn_produces_no_messages(self) -> None:
        assert turn_to_messages([TurnClosed(reason="cancelled")]) == []


class TestATurnWithTools:
    def test_calls_and_results_pair_up(self) -> None:
        wire = turn_to_messages(
            [
                TextDelta(text="Let me look. "),
                ToolCallReady(id="c1", name="fs__read", arguments={"path": "a"}),
                ToolResultEvent(call_id="c1", tool="fs__read", text="contents"),
                TextDelta(text="It says contents."),
                TurnClosed(),
            ]
        )

        assert [m.role for m in wire] == [Role.ASSISTANT, Role.TOOL, Role.ASSISTANT]
        assert wire[0].tool_calls[0].id == "c1"
        assert wire[0].tool_calls[0].arguments == {"path": "a"}
        assert wire[1].tool_call_id == "c1"
        assert wire[1].content == "contents"
        assert wire[2].content == "It says contents."

    def test_parallel_calls_each_get_their_own_tool_message(self) -> None:
        """A turn's worth of emotions is the everyday case (ADR 3), and every one of them
        needs its own answer or the model matches a result to nothing."""
        wire = turn_to_messages(
            [
                ToolCallReady(id="c1", name="hera__emotion"),
                ToolCallReady(id="c2", name="hera__emotion"),
                ToolResultEvent(call_id="c1", tool="hera__emotion", text="noted"),
                ToolResultEvent(call_id="c2", tool="hera__emotion", text="noted"),
            ]
        )

        assert [m.role for m in wire] == [Role.ASSISTANT, Role.TOOL, Role.TOOL]
        assert [m.tool_call_id for m in wire[1:]] == ["c1", "c2"]

    def test_two_rounds_of_tools_become_two_assistant_messages(self) -> None:
        wire = turn_to_messages(
            [
                ToolCallReady(id="c1", name="fs__read"),
                ToolResultEvent(call_id="c1", tool="fs__read", text="one"),
                TextDelta(text="Now the other. "),
                ToolCallReady(id="c2", name="fs__read"),
                ToolResultEvent(call_id="c2", tool="fs__read", text="two"),
                TextDelta(text="Done."),
            ]
        )
        assert [m.role for m in wire] == [
            Role.ASSISTANT,
            Role.TOOL,
            Role.ASSISTANT,
            Role.TOOL,
            Role.ASSISTANT,
        ]

    def test_a_failed_call_still_answers_the_model(self) -> None:
        """A failure is information the model can act on. Omitting it leaves a hole it
        notices and often tries to fill by calling again."""
        wire = turn_to_messages(
            [
                ToolCallReady(id="c1", name="fs__read"),
                ToolResultEvent(
                    call_id="c1", tool="fs__read", ok=False, failure="denied", text="not allowed"
                ),
            ]
        )
        assert wire[1].content == "not allowed"

    def test_a_call_that_was_never_run_is_said_so(self) -> None:
        """A turn paused on a permission card, reloaded. An unanswered tool_call_id is worse
        than an answer saying it did not happen."""
        wire = turn_to_messages(
            [
                ToolCallReady(id="c1", name="fs__read"),
                TurnClosed(reason="awaiting_permission"),
            ]
        )
        assert wire[1].role is Role.TOOL
        assert "never run" in wire[1].content


class TestWholeConversations:
    def test_user_and_assistant_messages_alternate_through(self) -> None:
        history = build_history(
            [
                Message(owner_id=UUID(int=1), chat_id=UUID(int=2), role="user", content="Hi"),
                stored(TextDelta(text="Hello."), TurnClosed()),
                Message(owner_id=UUID(int=1), chat_id=UUID(int=2), role="user", content="More?"),
            ]
        )
        assert [(m.role, m.content) for m in history] == [
            (Role.USER, "Hi"),
            (Role.ASSISTANT, "Hello."),
            (Role.USER, "More?"),
        ]

    def test_an_empty_user_message_is_skipped(self) -> None:
        """A resume creates no new user message, and sending an empty one would look to the
        model like the person said nothing on purpose."""
        history = build_history(
            [Message(owner_id=UUID(int=1), chat_id=UUID(int=2), role="user", content="   ")]
        )
        assert history == []

    def test_events_survive_the_database(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        chat = chats.create(owner_id)
        message = messages.start_assistant_message(chat)
        messages.record(
            message,
            [
                TextDelta(text="Let me look. "),
                ToolCallReady(id="c1", name="fs__read"),
                ToolResultEvent(call_id="c1", tool="fs__read", text="contents"),
                TurnClosed(),
            ],
        )

        reloaded = messages.get_or_raise(message.id)
        wire = turn_to_messages(events_of(reloaded))

        assert [m.role for m in wire] == [Role.ASSISTANT, Role.TOOL]
        assert wire[1].content == "contents"

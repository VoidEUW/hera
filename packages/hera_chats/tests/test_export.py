"""What `for_export` turns a chat into — one document, thinking left out, everything else a
line rather than a silence."""

from __future__ import annotations

from uuid import UUID

from hera_chats import (
    CHAT_EVENT_ADAPTER,
    AnswerGiven,
    AnswerRequired,
    Chat,
    ChatEvent,
    Message,
    PermissionDecided,
    PermissionRequired,
    SkillSelected,
    ToolResultEvent,
    TurnClosed,
    for_export,
)
from hera_providers import TextDelta, ThinkingDelta, ToolCallReady


def _chat(owner_id: UUID, *, title: str = "") -> Chat:
    return Chat(owner_id=owner_id, title=title)


def _message(owner_id: UUID, chat_id: UUID, *, role: str, events: list[ChatEvent]) -> Message:
    dumped = [CHAT_EVENT_ADAPTER.dump_python(event, mode="json") for event in events]
    return Message(owner_id=owner_id, chat_id=chat_id, role=role, events=dumped)


def _user(owner_id: UUID, chat_id: UUID, text: str) -> Message:
    return Message(owner_id=owner_id, chat_id=chat_id, role="user", content=text)


class TestFrontMatter:
    def test_the_title_and_created_date_open_the_document(self, owner_id: UUID) -> None:
        chat = _chat(owner_id, title="Kerberos")
        text = for_export(chat, [])
        assert text.startswith("---\ntitle: Kerberos\ncreated: ")
        assert "\n---\n" in text

    def test_an_untitled_chat_says_so(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assert "title: Untitled" in for_export(chat, [])


class TestTheConversation:
    def test_a_plain_exchange_reads_as_two_sections(self, owner_id: UUID) -> None:
        chat = _chat(owner_id, title="Weather")
        user = _user(owner_id, chat.id, "How's the weather?")
        assistant = _message(owner_id, chat.id, role="assistant", events=[TextDelta(text="Sunny.")])
        text = for_export(chat, [user, assistant])
        assert "## You\n\nHow's the weather?" in text
        assert "## Hera\n\nSunny." in text

    def test_thinking_never_reaches_the_document(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[ThinkingDelta(text="let me consider"), TextDelta(text="Sure.")],
        )
        text = for_export(chat, [assistant])
        assert "let me consider" not in text
        assert "Sure." in text

    def test_an_assistant_message_with_nothing_visible_gets_no_section(
        self, owner_id: UUID
    ) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id, chat.id, role="assistant", events=[ThinkingDelta(text="hmm")]
        )
        assert "## Hera" not in for_export(chat, [assistant])


class TestASkillSelection:
    def test_reads_as_one_line_with_why(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[SkillSelected(skill="tdd", reason="pinned"), TextDelta(text="Done.")],
        )
        text = for_export(chat, [assistant])
        assert "> skill: **tdd** (pinned)" in text


class TestAToolCall:
    def test_a_successful_call_reads_ok(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[
                ToolCallReady(id="c1", name="fs__read_file", arguments={"path": "a.txt"}),
                ToolResultEvent(call_id="c1", tool="fs__read_file", text="contents"),
                TextDelta(text="It says contents."),
            ],
        )
        text = for_export(chat, [assistant])
        assert "> called `fs__read_file` — ok" in text
        assert "<details>" in text
        assert "path: 'a.txt'" in text
        assert "contents" in text

    def test_a_failed_call_names_the_failure(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[
                ToolCallReady(id="c1", name="fs__delete_file", arguments={}),
                ToolResultEvent(call_id="c1", tool="fs__delete_file", ok=False, failure="denied"),
            ],
        )
        text = for_export(chat, [assistant])
        assert "> called `fs__delete_file` — failed: denied" in text

    def test_a_call_still_awaiting_permission_says_so(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[
                ToolCallReady(id="c1", name="fs__write_file", arguments={}),
                PermissionRequired(call_id="c1", tool="fs__write_file", reason="it writes"),
            ],
        )
        text = for_export(chat, [assistant])
        assert "> called `fs__write_file` — awaiting a decision" in text

    def test_a_decided_but_unresolved_call_reads_the_decision(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[
                ToolCallReady(id="c1", name="fs__write_file", arguments={}),
                PermissionRequired(call_id="c1", tool="fs__write_file"),
                PermissionDecided(call_id="c1", allowed=False),
            ],
        )
        text = for_export(chat, [assistant])
        assert "> called `fs__write_file` — denied" in text

    def test_a_call_with_no_arguments_and_no_result_text_has_no_detail_block(
        self, owner_id: UUID
    ) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[
                ToolCallReady(id="c1", name="hera__scratch_list", arguments={}),
                ToolResultEvent(call_id="c1", tool="hera__scratch_list", text=""),
            ],
        )
        assert "<details>" not in for_export(chat, [assistant])


class TestAQuestion:
    def test_asked_and_answered(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[
                AnswerRequired(
                    call_id="c1", tool="hera__ask", question="Which one?", kind="choice"
                ),
                AnswerGiven(call_id="c1", text="The second."),
            ],
        )
        text = for_export(chat, [assistant])
        assert "> asked: Which one? — replied: The second." in text

    def test_asked_and_still_waiting(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[AnswerRequired(call_id="c1", tool="hera__ask", question="Which one?")],
        )
        text = for_export(chat, [assistant])
        assert "> asked: Which one? — awaiting a reply" in text


class TestATurnThatDidNotFinishCleanly:
    def test_a_completed_turn_is_silent_about_it(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[TextDelta(text="Done."), TurnClosed(reason="completed")],
        )
        assert "turn ended" not in for_export(chat, [assistant])

    def test_a_cancelled_turn_says_so(self, owner_id: UUID) -> None:
        chat = _chat(owner_id)
        assistant = _message(
            owner_id,
            chat.id,
            role="assistant",
            events=[TextDelta(text="Part of an ans"), TurnClosed(reason="cancelled")],
        )
        assert "*(turn ended: cancelled)*" in for_export(chat, [assistant])

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


class TestAttachments:
    """A file is data on the message, not text pasted into it — so the interface can draw a
    chip without parsing prose, and the model still reads the file."""

    def test_a_file_reaches_the_model_named_and_fenced(self) -> None:
        from hera_chats import Attachment, compose

        composed = compose("What is wrong here?", [Attachment(name="a.py", text="x = 1")])

        assert composed.index("What is wrong here?") < composed.index("a.py")
        assert "Attached file: a.py" in composed
        assert "x = 1" in composed

    def test_a_message_with_no_files_is_untouched(self) -> None:
        from hera_chats import compose

        assert compose("Explain Kerberos", []) == "Explain Kerberos"

    def test_a_message_without_a_picture_is_still_a_plain_string(self) -> None:
        """The shape every OpenAI-compatible server has served since before parts existed. An
        installation that never attaches an image never sends a differently shaped request."""
        from hera_chats import Attachment, content_of

        assert content_of("Explain Kerberos", []) == "Explain Kerberos"
        assert isinstance(content_of("look", [Attachment(name="a.py", text="x = 1")]), str)

    def test_a_picture_becomes_a_content_part_beside_the_words(self) -> None:
        from hera_chats import Attachment, content_of
        from hera_providers import ImagePart, TextPart

        url = "data:image/png;base64,iVBORw0KGgo="
        content = content_of(
            "what is this?",
            [Attachment(name="shot.png", data_url=url, media_type="image/png", bytes=9)],
        )

        assert isinstance(content, list)
        words, picture = content
        assert isinstance(words, TextPart)
        assert isinstance(picture, ImagePart)
        assert picture.url == url
        # Named in the text as well, because "the second screenshot" has to refer to something.
        assert "Attached image: shot.png" in words.text
        assert url not in words.text, "the bytes go in the block, not into the prose"

    def test_a_picture_on_its_own_sends_no_empty_text_part(self) -> None:
        from hera_chats import Attachment, content_of

        picture = Attachment(
            name="a.png", data_url="data:image/png;base64,x", media_type="image/png"
        )
        content = content_of("", [picture])

        assert isinstance(content, list)
        # The name is words, so there is still a text part -- what there is never is an empty one.
        assert all(getattr(part, "text", "x") for part in content)

    def test_text_and_pictures_travel_in_the_same_message(self) -> None:
        from hera_chats import Attachment, content_of
        from hera_providers import ImagePart

        content = content_of(
            "compare these",
            [
                Attachment(name="a.py", text="x = 1"),
                Attachment(
                    name="b.png", data_url="data:image/png;base64,y", media_type="image/png"
                ),
            ],
        )

        assert isinstance(content, list)
        assert [type(part) for part in content][-1] is ImagePart
        assert "x = 1" in content[0].text  # type: ignore[union-attr]

    def test_a_fence_inside_a_file_cannot_close_the_block_early(self) -> None:
        from hera_chats import Attachment, compose

        fence = "`" * 3
        composed = compose("look", [Attachment(name="r.md", text=f"a\n{fence}\nb\n{fence}\nc")])

        assert composed.count(f"\n{fence}\n") == 1, "only the opening fence stands alone"
        assert composed.endswith(fence)

    def test_a_file_survives_the_database_and_reaches_the_next_turn(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        from hera_chats import Attachment

        chat = chats.create(owner_id)
        messages.add_user_message(
            chat, "read this", [Attachment(name="notes.md", text="slide 14", bytes=8)]
        )

        wire = build_history(messages.for_chat(chat.id))

        assert len(wire) == 1
        assert "read this" in wire[0].content
        assert "Attached file: notes.md" in wire[0].content
        assert "slide 14" in wire[0].content

    def test_the_stored_message_keeps_only_what_was_typed(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        """`content` is the thing a person actually wrote. Composing happens when the wire
        message is built, which is why the sidebar and the bubble stay readable."""
        from hera_chats import Attachment

        chat = chats.create(owner_id)
        stored = messages.add_user_message(
            chat, "read this", [Attachment(name="notes.md", text="slide 14", bytes=8)]
        )

        assert stored.content == "read this"
        assert stored.attachments[0]["name"] == "notes.md"

    def test_a_file_on_its_own_is_a_fair_question(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        from hera_chats import Attachment

        chat = chats.create(owner_id)
        messages.add_user_message(chat, "", [Attachment(name="a.py", text="x = 1")])

        wire = build_history(messages.for_chat(chat.id))

        assert len(wire) == 1
        assert "a.py" in wire[0].content


class TestALongArgument:
    """A call's arguments are replayed under every later question, so a tool whose argument is a
    document — a page she published, a file she wrote — would sit in the prompt for the rest of
    the conversation and grow it by everything she has ever written."""

    def page(self, size: int = 8_000) -> ToolCallReady:
        return ToolCallReady(
            id="c1",
            name="hera__artifact_create",
            arguments={"name": "page.html", "content": "x" * size, "inline": False},
        )

    def test_a_document_sized_argument_is_cut_in_a_later_turn(self) -> None:
        history = build_history([stored(self.page(), TurnClosed())], max_argument_chars=1_000)

        content = history[0].tool_calls[0].arguments["content"]
        assert len(content) < 1_200
        assert "more characters" in content

    def test_the_short_arguments_beside_it_are_untouched(self) -> None:
        """The rule is about size and not about which tool it is — this package does not know
        what a Hera tool is and must not learn."""
        history = build_history([stored(self.page(), TurnClosed())], max_argument_chars=1_000)

        arguments = history[0].tool_calls[0].arguments
        assert arguments["name"] == "page.html"
        assert arguments["inline"] is False

    def test_an_ordinary_call_is_not_touched_at_all(self) -> None:
        """A search query, a filename, a paragraph of a note all fit under the ceiling, which is
        what keeps this invisible in every turn that is not publishing a document."""
        call = ToolCallReady(id="c1", name="hera__search", arguments={"query": "kerberos tgt"})

        history = build_history([stored(call, TurnClosed())])

        assert history[0].tool_calls[0].arguments == {"query": "kerberos tgt"}

    def test_the_turn_in_progress_replays_its_own_calls_whole(self) -> None:
        """`turn_to_messages` is also what feeds a round of results back mid-turn, and what she
        just wrote is what she is still working on. Only the turns behind her are shortened."""
        wire = turn_to_messages([self.page(), TurnClosed()])

        assert len(wire[0].tool_calls[0].arguments["content"]) == 8_000

    def test_nothing_is_lost_from_what_was_stored(self) -> None:
        """The event keeps the whole argument, so the interface still shows what she really
        sent. This is only about the copy underneath the next question."""
        message = stored(self.page(), TurnClosed())

        build_history([message], max_argument_chars=1_000)

        assert len(message.events[0]["arguments"]["content"]) == 8_000

    def test_a_limit_of_zero_turns_it_off(self) -> None:
        history = build_history([stored(self.page(), TurnClosed())], max_argument_chars=0)

        assert len(history[0].tool_calls[0].arguments["content"]) == 8_000

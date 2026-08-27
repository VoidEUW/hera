"""The turn loop, against FakeProvider and a scripted tool layer.

The assertions worth reading are about *ordering* and about what happens when something goes
wrong. A turn is the one place in this system where five packages meet, and almost every bug it
can have is a bug about sequence: a tool result reaching the model after the next question, a
permission card that never closes the stream, a cancellation that loses the half-written answer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest
from chat_support import StubTools, WriteSkill, drain, kinds
from hera_providers.events import TurnEnd

from hera_chats import (
    PermissionRequired,
    SkillSelected,
    ToolResultEvent,
    TurnClosed,
    TurnContext,
    TurnOrchestrator,
)
from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_profiles import Profile
from hera_providers import (
    FakeProvider,
    ProviderError,
    Role,
    StreamInterrupted,
    TextDelta,
    ToolCallReady,
    Usage,
    text_turn,
    thinking_turn,
    tool_call,
    tool_turn,
)

Make = Callable[..., TurnOrchestrator]


class TestASimpleTurn:
    async def test_text_streams_through_and_the_turn_closes_once(
        self, make_orchestrator: Make
    ) -> None:
        turn = make_orchestrator(FakeProvider([text_turn("Hel", "lo.")])).begin(
            TurnContext(text="hi")
        )

        events = await drain(turn.stream())

        assert kinds(events) == ["text_delta", "text_delta", "turn_closed"]
        assert isinstance(events[-1], TurnClosed)
        assert events[-1].reason == "completed"
        assert events[-1].iterations == 1

    async def test_the_recorded_list_is_coalesced(self, make_orchestrator: Make) -> None:
        """Storing one row of JSON per token would make a reload replay the typing."""
        turn = make_orchestrator(FakeProvider([text_turn("Hel", "lo", "!")])).begin(
            TurnContext(text="hi")
        )
        await drain(turn.stream())

        assert kinds(turn.recorded) == ["text_delta", "turn_closed"]
        first = turn.recorded[0]
        assert isinstance(first, TextDelta)
        assert first.text == "Hello!"

    async def test_thinking_is_streamed_but_kept_apart(self, make_orchestrator: Make) -> None:
        turn = make_orchestrator(FakeProvider([thinking_turn("hmm", "Yes.")])).begin(
            TurnContext(text="hi")
        )
        assert kinds(await drain(turn.stream())) == [
            "thinking_delta",
            "text_delta",
            "turn_closed",
        ]

    async def test_the_prompt_frame_and_the_message_reach_the_provider(
        self, make_orchestrator: Make
    ) -> None:
        provider = FakeProvider([text_turn("ok")])
        await drain(
            make_orchestrator(provider).begin(TurnContext(text="Explain Kerberos")).stream()
        )

        request = provider.requests[0]
        assert request.messages[0].role is Role.SYSTEM
        assert "Hera" in request.messages[0].content
        assert request.messages[-1].content == "Explain Kerberos"

    async def test_history_sits_between_the_frame_and_the_question(
        self, make_orchestrator: Make
    ) -> None:
        """hera_prompts renders a frame and says the history goes in the middle. This is the
        middle."""
        from hera_providers import ChatMessage

        provider = FakeProvider([text_turn("ok")])
        history = [
            ChatMessage(role=Role.USER, content="earlier"),
            ChatMessage(role=Role.ASSISTANT, content="answered"),
        ]
        await drain(
            make_orchestrator(provider).begin(TurnContext(text="now", history=history)).stream()
        )

        contents = [m.content for m in provider.requests[0].messages]
        assert contents.index("earlier") < contents.index("now")
        assert contents.index("answered") < contents.index("now")

    async def test_the_prompt_fingerprint_is_recorded(self, make_orchestrator: Make) -> None:
        """Two answers that disagree are much easier to explain when you can tell whether
        they came from the same prompt."""
        turn = make_orchestrator(FakeProvider([text_turn("ok")])).begin(TurnContext(text="hi"))
        await drain(turn.stream())
        assert len(turn.prompt_fingerprint) == 64

    async def test_a_profile_shapes_the_prompt(
        self, make_orchestrator: Make, profile: Profile
    ) -> None:
        provider = FakeProvider([text_turn("ok")])
        profile.overrides = {"character": "You are terse to the point of rudeness."}
        await drain(
            make_orchestrator(provider).begin(TurnContext(text="hi", profile=profile)).stream()
        )
        assert "point of rudeness" in provider.requests[0].messages[0].content


class TestSkills:
    async def test_a_slash_command_selects_a_skill_and_is_stripped(
        self, make_orchestrator: Make, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd", body="Red, green, refactor.")
        provider = FakeProvider([text_turn("ok")])

        turn = make_orchestrator(provider).begin(TurnContext(text="/tdd how do I test this?"))
        events = await drain(turn.stream())

        assert isinstance(events[0], SkillSelected)
        assert events[0].skill == "tdd"
        assert events[0].reason == "pinned" or events[0].reason == "slash"
        assert provider.requests[0].messages[-1].content == "how do I test this?"

    async def test_the_skill_body_reaches_the_prompt_uncorrupted(
        self, make_orchestrator: Make, write_skill: WriteSkill
    ) -> None:
        """The reason Section.escape exists: a skill body is somebody else's code."""
        write_skill("tdd", body="assert count < limit && ready")
        provider = FakeProvider([text_turn("ok")])

        await drain(make_orchestrator(provider).begin(TurnContext(text="/tdd go")).stream())

        assert "count < limit && ready" in provider.requests[0].messages[0].content

    async def test_pins_come_from_the_profile_and_the_project_together(
        self, make_orchestrator: Make, write_skill: WriteSkill, profile: Profile
    ) -> None:
        from hera_chats.models import Project

        write_skill("writing")
        write_skill("house-style")
        profile.pinned_skills = ["writing"]
        project = Project(
            owner_id=profile.owner_id, slug="p", name="P", pinned_skills=["house-style"]
        )

        turn = make_orchestrator(FakeProvider([text_turn("ok")])).begin(
            TurnContext(text="hi", profile=profile, project=project)
        )
        events = await drain(turn.stream())

        assert [e.skill for e in events if isinstance(e, SkillSelected)] == [
            "writing",
            "house-style",
        ]

    async def test_project_instructions_reach_the_prompt(self, make_orchestrator: Make) -> None:
        from uuid import uuid4

        from hera_chats.models import Project

        provider = FakeProvider([text_turn("ok")])
        project = Project(
            owner_id=uuid4(), slug="hera", name="Hera", instructions="Always use British spelling."
        )
        await drain(
            make_orchestrator(provider).begin(TurnContext(text="hi", project=project)).stream()
        )
        assert "British spelling" in provider.requests[0].messages[0].content


class TestTheToolLoop:
    async def test_a_call_runs_and_the_answer_goes_back(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        provider = FakeProvider(
            [tool_turn(tool_call("fs__read_file", {"path": "a"})), text_turn("It says so.")]
        )

        turn = make_orchestrator(provider, tools).begin(TurnContext(text="read a"))
        events = await drain(turn.stream())

        assert kinds(events) == ["tool_call_ready", "tool_result", "text_delta", "turn_closed"]
        assert isinstance(events[-1], TurnClosed)
        assert events[-1].iterations == 2

    async def test_the_result_reaches_the_second_request_paired_to_its_call(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("done")])
        await drain(make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream())

        second = provider.requests[1].messages
        tool_messages = [m for m in second if m.role is Role.TOOL]
        assert tool_messages[0].tool_call_id == "call_fs__read_file"
        assert tool_messages[0].content == "ran fs__read_file"

    async def test_parallel_calls_are_dispatched_in_one_batch(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        """Running them one after another turns one round-trip into four (ADR 3)."""
        provider = FakeProvider(
            [
                tool_turn(
                    tool_call("hera__emotion", call_id="e1"),
                    tool_call("hera__emotion", call_id="e2"),
                ),
                text_turn("done"),
            ]
        )
        tools.catalogue_value = tools.catalogue_value  # unchanged; policy allows everything

        await drain(make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream())

        assert len(tools.dispatched) == 1
        assert [call.call_id for call in tools.dispatched[0]] == ["e1", "e2"]

    async def test_the_catalogue_is_offered_to_the_model(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        provider = FakeProvider([text_turn("ok")])
        await drain(make_orchestrator(provider, tools).begin(TurnContext(text="hi")).stream())

        assert [spec.name for spec in provider.requests[0].tools] == ["fs__read_file"]
        assert "fs__read_file" in provider.requests[0].messages[0].content

    async def test_no_registry_means_the_prompt_says_nothing_about_tools(
        self, make_orchestrator: Make
    ) -> None:
        """An empty catalogue reads to a model as "you have no tools" and earns a paragraph
        about it."""
        provider = FakeProvider([text_turn("ok")])
        await drain(make_orchestrator(provider).begin(TurnContext(text="hi")).stream())

        assert provider.requests[0].tools == []
        assert "tools:available" not in provider.requests[0].messages[0].content

    async def test_a_failing_tool_is_a_result_not_an_exception(
        self, make_orchestrator: Make
    ) -> None:
        from hera_tools import Failure, ToolResult

        tools = StubTools(
            results={
                "fs__read_file": ToolResult.failed(
                    call_id="", tool="fs__read_file", failure=Failure.TIMEOUT, text="gave up"
                )
            }
        )
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("oh well")])

        events = await drain(
            make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream()
        )

        result = next(e for e in events if isinstance(e, ToolResultEvent))
        assert result.failure == "timeout"
        assert not result.ok

    async def test_the_loop_is_bounded(self, make_orchestrator: Make, tools: StubTools) -> None:
        """A model stuck calling the same tool should cost seconds, and the interface should
        say so -- stopping silently looks like a short answer."""
        provider = FakeProvider(lambda request: tool_turn(tool_call("fs__read_file")))

        turn = make_orchestrator(provider, tools).begin(TurnContext(text="go"))
        events = await drain(turn.stream())

        assert isinstance(events[-1], TurnClosed)
        assert events[-1].reason == "max_iterations"
        assert events[-1].iterations == 4

    async def test_usage_is_added_up_across_round_trips(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        provider = FakeProvider(
            [
                [
                    ToolCallReady(id="c1", name="fs__read_file"),
                    TurnEnd(reason="tool_calls", usage=Usage(total_tokens=10)),
                ],
                text_turn("done", usage=Usage(total_tokens=7)),
            ]
        )

        events = await drain(
            make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream()
        )

        closed = events[-1]
        assert isinstance(closed, TurnClosed)
        assert closed.usage is not None
        assert closed.usage.total_tokens == 17

    async def test_usage_stays_none_when_the_server_reports_none(
        self, make_orchestrator: Make
    ) -> None:
        """Many local servers do not report it, and a zero is a lie a context meter would
        draw."""
        turn = make_orchestrator(FakeProvider([text_turn("ok")])).begin(TurnContext(text="hi"))
        events = await drain(turn.stream())
        assert isinstance(events[-1], TurnClosed)
        assert events[-1].usage is None


class TestPermissions:
    async def test_an_ask_stops_the_turn_and_asks(
        self, make_orchestrator: Make, ask_policy: Policy
    ) -> None:
        tools = StubTools(policy=ask_policy)
        provider = FakeProvider([tool_turn(tool_call("fs__read_file", {"path": "a"}))])

        turn = make_orchestrator(provider, tools).begin(TurnContext(text="go"))
        events = await drain(turn.stream())

        assert kinds(events) == ["tool_call_ready", "permission_required", "turn_closed"]
        card = events[1]
        assert isinstance(card, PermissionRequired)
        assert card.tool == "fs__read_file"
        assert card.arguments == {"path": "a"}
        assert card.reason == "it writes to disk"
        assert isinstance(events[-1], TurnClosed)
        assert events[-1].reason == "awaiting_permission"

    async def test_nothing_was_dispatched_while_waiting(
        self, make_orchestrator: Make, ask_policy: Policy
    ) -> None:
        tools = StubTools(policy=ask_policy)
        provider = FakeProvider([tool_turn(tool_call("fs__read_file"))])

        await drain(make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream())

        assert tools.dispatched == []

    async def test_a_deny_is_not_a_question(self, make_orchestrator: Make) -> None:
        """Nobody is being asked. The call will not run, and the model is told so."""
        policy = Policy(
            base=PermissionSet(
                rules=[Rule(pattern="fs__*", decision=Decision.DENY, reason="never")]
            ),
            fallback=Decision.ALLOW,
        )
        tools = StubTools(policy=policy)
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("fine")])

        events = await drain(
            make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream()
        )

        assert "permission_required" not in kinds(events)
        result = next(e for e in events if isinstance(e, ToolResultEvent))
        assert result.failure == "denied"

    async def test_confirming_resumes_the_same_message(
        self, make_orchestrator: Make, ask_policy: Policy
    ) -> None:
        """The turn closed and its events were persisted; answering the card starts a new
        turn that continues the same assistant message."""
        tools = StubTools(policy=ask_policy)
        paused = await drain(
            make_orchestrator(FakeProvider([tool_turn(tool_call("fs__read_file"))]), tools)
            .begin(TurnContext(text="go"))
            .stream()
        )

        resumed = make_orchestrator(FakeProvider([text_turn("It said so.")]), tools).begin(
            TurnContext(text="", resume=paused, confirmed=["call_fs__read_file"])
        )
        events = await drain(resumed.stream())

        assert kinds(events) == ["tool_result", "text_delta", "turn_closed"]
        assert tools.confirmed_seen == [("call_fs__read_file",)]

    async def test_a_resumed_turn_keeps_the_events_it_already_had(
        self, make_orchestrator: Make, ask_policy: Policy
    ) -> None:
        tools = StubTools(policy=ask_policy)
        paused = await drain(
            make_orchestrator(
                FakeProvider([tool_turn(tool_call("fs__read_file"), text="Looking. ")]), tools
            )
            .begin(TurnContext(text="go"))
            .stream()
        )

        resumed = make_orchestrator(FakeProvider([text_turn("Done.")]), tools).begin(
            TurnContext(text="", resume=paused, confirmed=["call_fs__read_file"])
        )
        await drain(resumed.stream())

        assert kinds(resumed.recorded) == [
            "text_delta",
            "tool_call_ready",
            "permission_required",
            "turn_closed",
            "tool_result",
            "text_delta",
            "turn_closed",
        ]

    async def test_refusing_answers_the_model_instead_of_hanging(
        self, make_orchestrator: Make, ask_policy: Policy
    ) -> None:
        tools = StubTools(policy=ask_policy)
        paused = await drain(
            make_orchestrator(FakeProvider([tool_turn(tool_call("fs__read_file"))]), tools)
            .begin(TurnContext(text="go"))
            .stream()
        )

        resumed = make_orchestrator(FakeProvider([text_turn("Understood.")]), tools).begin(
            TurnContext(text="", resume=paused, denied=["call_fs__read_file"])
        )
        events = await drain(resumed.stream())

        result = next(e for e in events if isinstance(e, ToolResultEvent))
        assert result.failure == "denied"
        assert not result.ok
        assert tools.dispatched == []

    async def test_an_answered_call_is_not_asked_about_twice(
        self, make_orchestrator: Make, ask_policy: Policy
    ) -> None:
        """A model that reuses a call id after a resume must not re-open the card it was
        just answered -- the person would be asked the same question in a loop."""
        tools = StubTools(policy=ask_policy)
        paused = await drain(
            make_orchestrator(FakeProvider([tool_turn(tool_call("fs__read_file"))]), tools)
            .begin(TurnContext(text="go"))
            .stream()
        )

        resumed = make_orchestrator(
            FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("done")]), tools
        ).begin(TurnContext(text="", resume=paused, confirmed=["call_fs__read_file"]))
        events = await drain(resumed.stream())

        assert "permission_required" not in kinds(events)
        assert isinstance(events[-1], TurnClosed)
        assert events[-1].reason == "completed"

    async def test_a_resumed_turn_does_not_re_select_skills(
        self, make_orchestrator: Make, ask_policy: Policy, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        tools = StubTools(policy=ask_policy)
        paused = await drain(
            make_orchestrator(FakeProvider([tool_turn(tool_call("fs__read_file"))]), tools)
            .begin(TurnContext(text="/tdd go"))
            .stream()
        )

        resumed = make_orchestrator(FakeProvider([text_turn("done")]), tools).begin(
            TurnContext(text="", resume=paused, confirmed=["call_fs__read_file"])
        )
        events = await drain(resumed.stream())

        assert len([e for e in events if isinstance(e, SkillSelected)]) == 0


class TestWhenThingsGoWrong:
    async def test_a_dead_provider_closes_the_turn_rather_than_raising(
        self, make_orchestrator: Make
    ) -> None:
        """An exception escaping mid-stream is a connection that just stops, which the
        browser cannot tell from a network problem."""
        provider = FakeProvider([ProviderError("endpoint unreachable")])

        turn = make_orchestrator(provider).begin(TurnContext(text="hi"))
        events = await drain(turn.stream())

        assert isinstance(events[-1], TurnClosed)
        assert events[-1].reason == "failed"
        assert "unreachable" in events[-1].error

    async def test_a_broken_stream_keeps_what_arrived(self, make_orchestrator: Make) -> None:
        """StreamInterrupted is the one to special-case: part of the answer did arrive, and
        it is worth persisting rather than throwing away."""

        class BreaksMidSentence:
            """Streams a little and then loses the connection."""

            async def stream(self, request: object) -> AsyncIterator[object]:
                yield TextDelta(text="Half an ans")
                raise StreamInterrupted("connection dropped")

            async def aclose(self) -> None:
                return None

        turn = make_orchestrator(BreaksMidSentence()).begin(TurnContext(text="hi"))
        events = await drain(turn.stream())

        assert isinstance(events[-1], TurnClosed)
        assert events[-1].reason == "cancelled"
        assert turn.recorded[0] == TextDelta(text="Half an ans")

    async def test_a_cancelled_turn_still_has_a_terminator(self, make_orchestrator: Make) -> None:
        """Whatever happened before the cancellation has to be persistable, and a persisted
        list with no terminator is one the interface renders as still streaming."""
        provider = FakeProvider([text_turn("one", "two", "three")])
        turn = make_orchestrator(provider).begin(TurnContext(text="hi"))

        stream = turn.stream()
        await anext(stream)
        await stream.aclose()

        assert isinstance(turn.recorded[-1], TurnClosed)
        assert turn.close_reason == "cancelled"

    async def test_a_model_asking_for_tools_with_none_configured_is_told_so(
        self, make_orchestrator: Make
    ) -> None:
        """A model can invent a call even when it was offered nothing. Answering it beats
        leaving the tool_call_id unanswered, which it notices and tries to fill again."""
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("ah, none")])

        events = await drain(make_orchestrator(provider).begin(TurnContext(text="go")).stream())

        result = next(e for e in events if isinstance(e, ToolResultEvent))
        assert result.failure == "denied"
        assert "no tools are configured" in result.text

    async def test_close_reason_reports_cancelled_for_a_turn_that_never_ran(
        self, make_orchestrator: Make
    ) -> None:
        turn = make_orchestrator(FakeProvider([text_turn("ok")])).begin(TurnContext(text="hi"))
        assert turn.close_reason == "cancelled"

    async def test_the_terminator_is_written_once(self, make_orchestrator: Make) -> None:
        turn = make_orchestrator(FakeProvider([text_turn("ok")])).begin(TurnContext(text="hi"))
        await drain(turn.stream())
        assert kinds(turn.recorded).count("turn_closed") == 1

    async def test_hanging_up_after_the_last_event_does_not_re_close(
        self, make_orchestrator: Make
    ) -> None:
        """A browser that disconnects the moment the answer finishes. A second terminator
        would make a completed turn read as cancelled -- the interface looks at the last
        event to decide which it was."""
        turn = make_orchestrator(FakeProvider([text_turn("ok")])).begin(TurnContext(text="hi"))

        stream = turn.stream()
        seen = []
        async for event in stream:
            seen.append(event)
            if isinstance(event, TurnClosed):
                break
        await stream.aclose()

        assert kinds(turn.recorded).count("turn_closed") == 1
        assert turn.close_reason == "completed"


class TestTheProtocol:
    def test_a_real_registry_satisfies_the_tools_port(self) -> None:
        """The protocol narrows hera_tools.ToolRegistry to the three methods a turn uses. If
        it ever stops matching, the application stops compiling rather than the tests."""
        from hera_chats import Tools
        from hera_tools import ToolRegistry

        assert issubclass(ToolRegistry, Tools) or isinstance(ToolRegistry([], policy=None), Tools)

    def test_the_stub_satisfies_it_too(self, tools: StubTools) -> None:
        from hera_chats import Tools

        assert isinstance(tools, Tools)


@pytest.mark.parametrize("text", ["", "   "])
async def test_an_empty_message_sends_no_user_turn(make_orchestrator: Make, text: str) -> None:
    """A resume has no new user message, and an empty one reads to the model as somebody
    deliberately saying nothing."""
    provider = FakeProvider([text_turn("ok")])
    await drain(make_orchestrator(provider).begin(TurnContext(text=text)).stream())

    assert all(m.text.strip() for m in provider.requests[0].messages)

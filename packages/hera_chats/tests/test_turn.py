"""The turn loop, against FakeProvider and a scripted tool layer.

The assertions worth reading are about *ordering* and about what happens when something goes
wrong. A turn is the one place in this system where five packages meet, and almost every bug it
can have is a bug about sequence: a tool result reaching the model after the next question, a
permission card that never closes the stream, a cancellation that loses the half-written answer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from uuid import uuid4

import pytest
from chat_support import StubTools, WriteSkill, drain, kinds
from hera_providers.events import TurnEnd

from hera_chats import (
    AnswerRequired,
    Chat,
    ChatsSettings,
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
    ChatRequest,
    Event,
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

        assert kinds(events) == [
            # `tool_call_started` is streamed and never recorded -- it says *she has begun
            # calling this* while the arguments are still arriving. Asserted here rather than
            # filtered out, because the sequence a person sees is what this test is about.
            "tool_call_started",
            "tool_call_ready",
            "tool_result",
            "text_delta",
            "turn_closed",
        ]
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


class TestWhenSheKeepsAskingTheSameThing:
    """The observed failure: asked for a figure it could not find, the model ran the *same*
    search four times, spent its whole budget on it, and was cut off mid-sentence. Every call
    succeeded — they simply did not contain the answer, so nothing in the loop noticed."""

    async def test_a_third_identical_call_is_not_run(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        provider = FakeProvider(lambda request: tool_turn(tool_call("fs__read_file", {"p": "a"})))

        await drain(make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream())

        # Twice, not once: the turn cannot know which tools are idempotent, and reading a file
        # after writing it is the same call with a legitimately different answer.
        assert len(tools.dispatched) == 2

    async def test_the_refusal_says_the_words_did_not_work(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        """The whole point. A model that is told nothing keeps searching; one that is told the
        query has been tried can change it or give up honestly."""
        provider = FakeProvider(lambda request: tool_turn(tool_call("fs__read_file", {"p": "a"})))

        events = await drain(
            make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream()
        )

        refusals = [
            event
            for event in events
            if isinstance(event, ToolResultEvent) and event.failure == "repeated"
        ]
        assert refusals
        assert "already made this exact call" in refusals[0].text
        assert not refusals[0].ok

    async def test_a_different_argument_is_a_different_call(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        """Otherwise the guard would stop real research on its third search."""
        queries = iter(["a", "b", "c", "d"])
        provider = FakeProvider(
            lambda request: tool_turn(tool_call("fs__read_file", {"p": next(queries, "z")}))
        )

        await drain(make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream())

        assert len(tools.dispatched) >= 4

    async def test_key_order_does_not_make_a_new_call(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        """A model does not emit its keys in a stable order, and two calls that differ only in
        that are the same request."""
        orders = iter([{"a": 1, "b": 2}, {"b": 2, "a": 1}, {"a": 1, "b": 2}])
        provider = FakeProvider(
            lambda request: tool_turn(tool_call("fs__read_file", next(orders, {"a": 1, "b": 2})))
        )

        await drain(make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream())

        assert len(tools.dispatched) == 2

    async def test_the_budget_ending_still_produces_an_answer(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        """It used to end on whatever half-sentence preceded the last batch of calls, with
        those results never shown to the model at all. Now the tools are withheld for one final
        round, which is the only thing that reliably stops a model asking for more."""
        rounds = 0

        def script(request: ChatRequest) -> Sequence[Event]:
            # Keyed on whether the request carried any tools, which is what the final round
            # withholds. Asserting on the *arithmetic* rather than on a round number, since the
            # ceiling is a setting and this behaviour is not.
            nonlocal rounds
            rounds += 1
            if request.tools:
                return tool_turn(tool_call("fs__read_file", {"p": str(rounds)}))
            return text_turn("Here is what I found, and what I could not.")

        provider = FakeProvider(script)
        events = await drain(
            make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream()
        )

        assert isinstance(events[-1], TurnClosed)
        assert events[-1].reason == "max_iterations"
        text = "".join(e.text for e in events if isinstance(e, TextDelta))
        assert "what I could not" in text

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

        assert kinds(events) == [
            "tool_call_started",
            "tool_call_ready",
            "permission_required",
            "turn_closed",
        ]
        card = events[2]
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
        first = make_orchestrator(
            FakeProvider([tool_turn(tool_call("fs__read_file"), text="Looking. ")]), tools
        ).begin(TurnContext(text="go"))
        await drain(first.stream())

        # `recorded` and not the drained stream: the application resumes from what was
        # *persisted*, and the two now differ by the `tool_call_started` that is streamed and
        # never stored. Resuming from the stream would feed the turn an event it can never
        # receive in production.
        resumed = make_orchestrator(FakeProvider([text_turn("Done.")]), tools).begin(
            TurnContext(text="", resume=first.recorded, confirmed=["call_fs__read_file"])
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


class TestAskingBack:
    """`hera__ask` suspends the turn the way a permission card does — deliberately the same
    mechanism, per ``docs/tooling.md`` § 4, rather than a second one beside it."""

    async def test_a_question_stops_the_turn(self, make_orchestrator: Make) -> None:
        tools = StubTools()
        provider = FakeProvider(
            [tool_turn(tool_call("hera__ask", {"question": "Which slide deck?", "kind": "unsure"}))]
        )

        events = await drain(
            make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream()
        )

        assert kinds(events) == [
            "tool_call_started",
            "tool_call_ready",
            "answer_required",
            "turn_closed",
        ]
        card = events[2]
        assert isinstance(card, AnswerRequired)
        assert card.question == "Which slide deck?"
        assert card.kind == "unsure"
        assert isinstance(events[-1], TurnClosed)
        assert events[-1].reason == "awaiting_answer"

    async def test_the_question_is_never_dispatched(self, make_orchestrator: Make) -> None:
        """It is not work for a tool. The server has a body for it that refuses, which is what
        a caller outside a turn gets; inside one it never reaches the registry at all."""
        tools = StubTools()
        provider = FakeProvider([tool_turn(tool_call("hera__ask", {"question": "Which?"}))])

        await drain(make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream())

        assert tools.dispatched == []

    async def test_a_reply_becomes_the_calls_result(self, make_orchestrator: Make) -> None:
        """The trick, stated as a test: nothing on the model's side of the loop learns that a
        person was in it. The words arrive where a tool's output would have."""
        tools = StubTools()
        paused = await drain(
            make_orchestrator(
                FakeProvider([tool_turn(tool_call("hera__ask", {"question": "Which?"}))]), tools
            )
            .begin(TurnContext(text="go"))
            .stream()
        )

        resumed = make_orchestrator(
            FakeProvider([text_turn("The second one, then.")]), tools
        ).begin(TurnContext(text="", resume=paused, answers={"call_hera__ask": "The 2024 one."}))
        events = await drain(resumed.stream())

        assert kinds(events) == ["tool_result", "text_delta", "turn_closed"]
        result = events[0]
        assert isinstance(result, ToolResultEvent)
        assert result.ok
        assert "The 2024 one." in result.text
        # Still never dispatched, on the way back through either.
        assert tools.dispatched == []

    async def test_an_empty_reply_is_an_answer_rather_than_a_failure(
        self, make_orchestrator: Make
    ) -> None:
        """Saying nothing is a thing a person may do. Failing the call would tell her the
        question was broken instead of that it went unanswered."""
        tools = StubTools()
        paused = await drain(
            make_orchestrator(
                FakeProvider([tool_turn(tool_call("hera__ask", {"question": "Which?"}))]), tools
            )
            .begin(TurnContext(text="go"))
            .stream()
        )

        resumed = make_orchestrator(FakeProvider([text_turn("Carrying on.")]), tools).begin(
            TurnContext(text="", resume=paused, answers={"call_hera__ask": "   "})
        )
        events = await drain(resumed.stream())

        result = events[0]
        assert isinstance(result, ToolResultEvent)
        assert result.ok
        assert "no answer" in result.text

    async def test_the_question_is_not_asked_twice(self, make_orchestrator: Make) -> None:
        """A resumed turn must not re-pose the question it was resumed to settle — which is
        what would happen if the call were only matched on its name."""
        tools = StubTools()
        paused = await drain(
            make_orchestrator(
                FakeProvider([tool_turn(tool_call("hera__ask", {"question": "Which?"}))]), tools
            )
            .begin(TurnContext(text="go"))
            .stream()
        )

        resumed = make_orchestrator(FakeProvider([text_turn("Right.")]), tools).begin(
            TurnContext(text="", resume=paused, answers={"call_hera__ask": "That one."})
        )
        events = await drain(resumed.stream())

        assert "answer_required" not in kinds(events)

    async def test_nothing_suspends_when_no_tool_is_named(
        self, builder: object, router: object
    ) -> None:
        """The default is an empty `asking_tools`, and a deployment that has not configured it
        runs `hera__ask` as an ordinary call — which the server itself then refuses."""
        tools = StubTools()
        orchestrator = TurnOrchestrator(
            provider=FakeProvider([tool_turn(tool_call("hera__ask", {"question": "Which?"}))]),
            builder=builder,  # type: ignore[arg-type]
            router=router,  # type: ignore[arg-type]
            registry=tools,
            settings=ChatsSettings(model="fake-model", max_iterations=2),
        )

        events = await drain(orchestrator.begin(TurnContext(text="go")).stream())

        assert "answer_required" not in kinds(events)
        assert tools.dispatched != []


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


class TestAnnouncingACall:
    """`tool_call_started` is streamed and never recorded.

    It exists because the name of a call arrives in the first stream fragment and the whole
    call only after the last, which on a real endpoint can be minutes later when the arguments
    are a document. What that means here is that the live event list and the persisted one are
    no longer the same list — so the two properties below are the contract the browser's
    reducer is written against, and both are asserted rather than assumed.
    """

    async def test_it_reaches_the_stream(self, make_orchestrator: Make, tools: StubTools) -> None:
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("done")])

        events = await drain(
            make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream()
        )

        assert kinds(events)[0] == "tool_call_started"

    async def test_it_is_not_recorded(self, make_orchestrator: Make, tools: StubTools) -> None:
        """The stored list is the record of what *happened*; this is progress. A call the
        stream broke off mid-argument never ran, and history already says so."""
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("done")])
        turn = make_orchestrator(provider, tools).begin(TurnContext(text="go"))

        await drain(turn.stream())

        assert "tool_call_started" not in kinds(turn.recorded)

    async def test_it_carries_the_id_the_call_is_dispatched_under(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        """What the browser pairs the two rows on. A mismatch is a row that stays *running*
        for ever beside the finished one."""
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("done")])

        events = await drain(
            make_orchestrator(provider, tools).begin(TurnContext(text="go")).stream()
        )

        announced = next(e for e in events if e.type == "tool_call_started")
        ready = next(e for e in events if e.type == "tool_call_ready")
        assert announced.id == ready.id

    async def test_a_turn_with_no_calls_announces_nothing(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        events = await drain(
            make_orchestrator(FakeProvider([text_turn("hello")]), tools)
            .begin(TurnContext(text="hi"))
            .stream()
        )

        assert "tool_call_started" not in kinds(events)


class TestWhatACallIsToldAboutTheTurn:
    """ADR 12: a tool cannot know which conversation it is in unless the turn says so.

    What this package contributes is deliberately small — it holds a *key* it was given and
    pairs it with the chat it already has. It does not know that the key means anything to
    anybody, which is the same arrangement `asking_tools` has and for the same reason: the
    package that reads it is her own MCP server, and this one may not learn that it exists.
    """

    async def test_the_chat_id_travels_with_every_call(
        self, make_orchestrator: Make, tools: StubTools, settings: ChatsSettings
    ) -> None:
        chat = Chat(owner_id=uuid4(), title="")
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("done")])
        orchestrator = make_orchestrator(provider, tools)
        orchestrator.settings = settings.model_copy(update={"chat_meta_key": "hera/chatId"})

        await drain(orchestrator.begin(TurnContext(text="go", chat=chat)).stream())

        assert tools.context_seen == [{"hera/chatId": str(chat.id)}]

    async def test_no_key_configured_sends_nothing(
        self, make_orchestrator: Make, tools: StubTools
    ) -> None:
        """The default. A deployment that configures none of this is one where no tool asks
        which conversation it is in — not one that sends a blank field to every server."""
        chat = Chat(owner_id=uuid4(), title="")
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("done")])

        await drain(
            make_orchestrator(provider, tools).begin(TurnContext(text="go", chat=chat)).stream()
        )

        assert tools.context_seen == [{}]

    async def test_a_turn_with_no_chat_sends_nothing(
        self, make_orchestrator: Make, tools: StubTools, settings: ChatsSettings
    ) -> None:
        """Every other test in this file runs without one, and a turn outside a conversation is
        a script rather than a person waiting. The tool that needs a chat then says so."""
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("done")])
        orchestrator = make_orchestrator(provider, tools)
        orchestrator.settings = settings.model_copy(update={"chat_meta_key": "hera/chatId"})

        await drain(orchestrator.begin(TurnContext(text="go")).stream())

        assert tools.context_seen == [{}]

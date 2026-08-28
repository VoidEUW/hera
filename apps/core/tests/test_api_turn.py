"""The streaming turn, end to end over HTTP.

This is the test that says the spine works: a message goes in, Server-Sent Events come out in
the right frames, and what was persisted matches what was streamed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import pytest
from core_support import API, StubTools, WriteSkill, names, payload, sse
from httpx import ASGITransport, AsyncClient

from hera_core.app import create_app
from hera_core.scratch import FileScratchpad
from hera_core.wiring import Services
from hera_home import scratch_dir
from hera_mcp import BUILTIN_SERVER_NAME, TOOL_NAMES, build_builtin_server
from hera_permissions import PermissionSet, Policy
from hera_providers import FakeProvider, text_turn, thinking_turn, tool_call, tool_turn
from hera_skillsets import SkillLibrary, SkillLibraryPort
from hera_tools import ToolRegistry, ToolsSettings


async def open_chat(client: AsyncClient) -> str:
    response = await client.post(f"{API}/chats", json={})
    assert response.status_code == 201
    return str(response.json()["id"])


async def talk(client: AsyncClient, chat_id: str, text: str) -> list[tuple[str, Any]]:
    response = await client.post(f"{API}/chats/{chat_id}/messages", json={"text": text})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return sse(response)


class TestASimpleTurn:
    async def test_the_frames_are_the_events_plus_done(self, make_services: Any) -> None:
        services = make_services(FakeProvider([text_turn("Hel", "lo.")]))
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "hi")

        assert names(frames) == ["text_delta", "text_delta", "turn_closed", "done"]

    async def test_each_frame_is_named_by_the_events_own_type(self, make_services: Any) -> None:
        """The SSE event name and the ``type`` inside the JSON are the same string from the
        same place, so a listener and a stored event cannot disagree."""
        services = make_services(FakeProvider([thinking_turn("hmm", "Yes.")]))
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "hi")

        for name, body in frames:
            if name != "done":
                assert body["type"] == name

    async def test_done_carries_the_persisted_message(self, make_services: Any) -> None:
        """What makes the server render authoritative: the client throws away everything it
        drew optimistically and re-renders from this."""
        services = make_services(FakeProvider([text_turn("Hel", "lo.")]))
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "hi")

        message = payload(frames, "done")
        assert message["role"] == "assistant"
        assert message["content"] == "Hello."
        assert [event["type"] for event in message["events"]] == ["text_delta", "turn_closed"]

    async def test_the_stored_text_is_coalesced(self, make_services: Any) -> None:
        """Two text_delta frames streamed, one stored. Same variant, so the reload renders
        exactly what the live view did."""
        services = make_services(FakeProvider([text_turn("Hel", "lo.")]))
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "hi")

        assert names(frames).count("text_delta") == 2
        assert len(payload(frames, "done")["events"]) == 2

    async def test_a_reload_renders_the_same_thing(self, make_services: Any) -> None:
        services = make_services(FakeProvider([text_turn("Hello.")]))
        async with _client(services) as client:
            chat_id = await open_chat(client)
            streamed = payload(await talk(client, chat_id, "hi"), "done")

            reloaded = (await client.get(f"{API}/chats/{chat_id}")).json()

        assert reloaded["messages"][1]["events"] == streamed["events"]

    async def test_the_user_message_is_stored_too(self, make_services: Any) -> None:
        services = make_services(FakeProvider([text_turn("Hello.")]))
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "Explain Kerberos")
            detail = (await client.get(f"{API}/chats/{chat_id}")).json()

        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][0]["content"] == "Explain Kerberos"

    async def test_the_first_message_names_the_chat(self, make_services: Any) -> None:
        services = make_services(FakeProvider([text_turn("Hello.")]))
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "Explain Kerberos")
            detail = (await client.get(f"{API}/chats/{chat_id}")).json()

        assert detail["chat"]["title"] == "Explain Kerberos"

    async def test_a_second_turn_sees_the_first(self, make_services: Any) -> None:
        """History is rebuilt from the stored events, so this is also the proof that the
        round trip through the database is faithful."""
        services = make_services(FakeProvider([text_turn("One."), text_turn("Two.")]))
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "first")
            await talk(client, chat_id, "second")

        contents = [m.content for m in services.provider.requests[1].messages]
        assert "One." in contents
        assert "first" in contents


class TestSkillsAndTools:
    async def test_a_slash_command_shows_up_as_a_skill_frame(
        self, make_services: Any, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd", body="Red, green, refactor.")
        services = make_services(FakeProvider([text_turn("ok")]))
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "/tdd how do I test this?")

        assert names(frames)[0] == "skill_selected"
        assert payload(frames, "skill_selected")["skill"] == "tdd"

    async def test_using_a_skill_is_counted(
        self, make_services: Any, write_skill: WriteSkill
    ) -> None:
        """The only feedback loop that tells you retrieval is picking the wrong thing."""
        write_skill("tdd")
        services = make_services(FakeProvider([text_turn("ok")]))
        async with _client(services) as client:
            await talk(client, await open_chat(client), "/tdd go")
            skills = (await client.get(f"{API}/skills")).json()

        assert skills["skills"][0]["hits"] == 1

    async def test_a_tool_call_and_its_result_both_stream(
        self, make_services: Any, tools: StubTools
    ) -> None:
        provider = FakeProvider(
            [tool_turn(tool_call("fs__read_file", {"path": "a"})), text_turn("It says so.")]
        )
        services = make_services(provider, tools)
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "read a")

        assert names(frames) == [
            # `tool_call_started` reaches the browser and is never stored: the name is in the
            # first stream fragment and the whole call only after the last, which on a real
            # endpoint is minutes apart when the arguments are a document.
            "tool_call_started",
            "tool_call_ready",
            "tool_result",
            "text_delta",
            "turn_closed",
            "done",
        ]
        assert payload(frames, "tool_result")["text"] == "ran fs__read_file"


class TestARealMcpServer:
    """The same path, with no stub anywhere between the model and the tool.

    Everything above uses `StubTools`, which is right for testing the *turn* — but it means
    nothing in the suite would notice if the MCP round trip stopped working. Here the registry
    is a real `ToolRegistry`, the server is a real `MCPServer` from `hera_mcp` reached over the
    SDK's in-memory transport, and the skill body that comes back was read off disk by
    `hera_skillsets` through a port. What is faked is the model, and only the model.
    """

    async def test_her_own_tools_are_reachable_through_the_protocol(
        self, make_services: Any, write_skill: WriteSkill, mcp_registry: ToolRegistry
    ) -> None:
        write_skill("tdd", body="Red, green, refactor.")
        provider = FakeProvider(
            [
                tool_turn(
                    tool_call("hera__emotion", {"kind": "curious"}),
                    tool_call("hera__skill", {"name": "tdd"}),
                ),
                text_turn("Tests first, then."),
            ]
        )
        services = make_services(provider, mcp_registry)
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "how do I start?")

        results = {body["tool"]: body for name, body in frames if name == "tool_result"}
        assert results["hera__emotion"]["ok"]
        assert results["hera__emotion"]["text"] == "shown"
        # Read off disk, handed over a port, returned through the protocol.
        assert results["hera__skill"]["text"] == "Red, green, refactor."
        assert names(frames)[-2:] == ["turn_closed", "done"]

    async def test_a_scratchpad_write_lands_in_this_conversations_directory(
        self, make_services: Any, mcp_registry: ToolRegistry
    ) -> None:
        """The whole of ADR 12 in one assertion, with nothing stubbed between the model and the
        disk. What is being proved is the part that has no other way of being observed: the
        chat id was never in the model's arguments, and the file still landed under this chat
        and not another. A `contextvars` implementation passes every unit test above this one
        and fails here, because `ManagedServer` runs the call in a worker task created when the
        server connected.
        """
        provider = FakeProvider(
            [
                tool_turn(
                    tool_call("hera__scratch_write", {"name": "plan.md", "text": "1. read it"})
                ),
                text_turn("Noted."),
            ]
        )
        services = make_services(provider, mcp_registry)
        async with _client(services) as client:
            chat_id = await open_chat(client)
            frames = await talk(client, chat_id, "make a plan")

        assert payload(frames, "tool_result")["ok"]
        assert (scratch_dir(chat_id) / "plan.md").read_text() == "1. read it"
        # And the model was never offered the field it would have had to guess.
        written = provider.requests[0].tools
        schema = next(spec for spec in written if spec.name == "hera__scratch_write").parameters
        assert set(schema.get("properties", {})) == {"name", "text", "append"}

    async def test_she_reads_back_what_an_earlier_turn_wrote(
        self, make_services: Any, mcp_registry: ToolRegistry
    ) -> None:
        """The reason the scratchpad is worth building: the second turn picks it up without the
        first having to be replayed through the context window."""
        provider = FakeProvider(
            [
                tool_turn(
                    tool_call("hera__scratch_write", {"name": "plan.md", "text": "1. read it"})
                ),
                text_turn("Noted."),
                tool_turn(tool_call("hera__scratch_read", {"name": "plan.md"})),
                text_turn("Where we left off."),
            ]
        )
        services = make_services(provider, mcp_registry)
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "make a plan")
            frames = await talk(client, chat_id, "where were we?")

        assert payload(frames, "tool_result")["text"] == "1. read it"

    async def test_another_conversation_cannot_read_it(
        self, make_services: Any, mcp_registry: ToolRegistry
    ) -> None:
        """One server, two chats, and the only thing keeping them apart is the `_meta` the turn
        put on the call."""
        provider = FakeProvider(
            [
                tool_turn(tool_call("hera__scratch_write", {"name": "plan.md", "text": "mine"})),
                text_turn("Noted."),
                tool_turn(tool_call("hera__scratch_read", {"name": "plan.md"})),
                text_turn("Nothing there."),
            ]
        )
        services = make_services(provider, mcp_registry)
        async with _client(services) as client:
            await talk(client, await open_chat(client), "make a plan")
            frames = await talk(client, await open_chat(client), "where were we?")

        result = payload(frames, "tool_result")
        assert not result["ok"]
        assert "no file named" in result["text"]

    async def test_a_tool_that_fails_comes_back_as_a_result(
        self, make_services: Any, mcp_registry: ToolRegistry
    ) -> None:
        """`ToolError` from the server, not an exception in the turn: the model is told the
        skill does not exist and what does, and gets to correct itself."""
        provider = FakeProvider(
            [tool_turn(tool_call("hera__skill", {"name": "nope"})), text_turn("My mistake.")]
        )
        services = make_services(provider, mcp_registry)
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "load nope")

        result = payload(frames, "tool_result")
        assert not result["ok"]
        assert "no skill named" in result["text"]

    async def test_the_catalogue_reaches_the_model_as_function_specs(
        self, make_services: Any, mcp_registry: ToolRegistry
    ) -> None:
        """Her whole catalogue, named for the server it came from. Without this the model has
        the prompt and no way to act on it."""
        provider = FakeProvider([text_turn("nothing to do")])
        services = make_services(provider, mcp_registry)
        async with _client(services) as client:
            await talk(client, await open_chat(client), "hello")

        offered = {spec.name for spec in provider.requests[0].tools}
        # Against TOOL_NAMES rather than a literal list, because the assertion is *her whole
        # catalogue arrives*, not *these six do*. Spelled out, this test fails every time a tool
        # is added to her server, and the fix is always to paste the new name in — which is a
        # test that costs maintenance and catches nothing.
        assert offered == {f"{BUILTIN_SERVER_NAME}__{name}" for name in TOOL_NAMES}

    async def test_the_settings_screen_sees_the_server_it_is_talking_to(
        self, make_services: Any, mcp_registry: ToolRegistry
    ) -> None:
        services = make_services(FakeProvider([text_turn("ok")]), mcp_registry)
        async with _client(services) as client:
            servers = (await client.get(f"{API}/servers")).json()

        assert servers == [
            {"name": "hera", "connected": True, "tools": len(TOOL_NAMES), "failure": None}
        ]


@pytest.fixture
async def mcp_registry(skills_path: Any) -> AsyncIterator[ToolRegistry]:
    """Her own server, mounted the way the application mounts it, everything allowed.

    ``HERA_HOME`` points at a temporary directory with no ``mcp.json`` in it, so nothing
    external is mounted: a test that started somebody's Docker gateway would be a test nobody
    can run offline.
    """
    registry = ToolRegistry.open(
        policy=Policy(base=PermissionSet.of(allow=["*"])),
        settings=ToolsSettings(),
        builtin=build_builtin_server(
            skills=SkillLibraryPort(SkillLibrary(skills_path)),
            scratchpad=FileScratchpad(),
        ),
    )
    try:
        yield registry
    finally:
        await registry.aclose()


class TestAskingAgain:
    """Edit and try-again, which are one route because they are one idea."""

    async def test_editing_a_question_replaces_the_answer_that_followed_it(
        self, make_services: Any
    ) -> None:
        provider = FakeProvider([text_turn("About Kerberos."), text_turn("About Kerberos v5.")])
        services = make_services(provider)
        async with _client(services) as client:
            chat_id = await open_chat(client)
            first = payload(await talk(client, chat_id, "tell me about kerberos"), "done")
            asked = _first_user(await _detail(client, chat_id))

            frames = await _redo(client, chat_id, asked["id"], "tell me about kerberos v5")
            detail = await _detail(client, chat_id)

        assert payload(frames, "done")["content"] == "About Kerberos v5."
        # Two messages, not four: the old question and its answer are gone rather than hidden.
        assert [m["content"] for m in detail["messages"]] == [
            "tell me about kerberos v5",
            "About Kerberos v5.",
        ]
        assert first["id"] not in {m["id"] for m in detail["messages"]}

    async def test_the_model_never_sees_the_wording_that_was_replaced(
        self, make_services: Any
    ) -> None:
        """The point of deleting rather than flagging: history is the message list."""
        provider = FakeProvider([text_turn("One."), text_turn("Two.")])
        services = make_services(provider)
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "first wording")
            asked = _first_user(await _detail(client, chat_id))
            await _redo(client, chat_id, asked["id"], "second wording")

        contents = [m.content for m in provider.requests[1].messages]
        assert any("second wording" in content for content in contents)
        assert not any("first wording" in content for content in contents)

    async def test_trying_an_answer_again_replays_the_question_above_it(
        self, make_services: Any
    ) -> None:
        provider = FakeProvider([text_turn("Terse."), text_turn("Longer, with detail.")])
        services = make_services(provider)
        async with _client(services) as client:
            chat_id = await open_chat(client)
            answer = payload(await talk(client, chat_id, "explain it"), "done")

            frames = await _redo(client, chat_id, answer["id"])
            detail = await _detail(client, chat_id)

        assert payload(frames, "done")["content"] == "Longer, with detail."
        assert [m["content"] for m in detail["messages"]] == ["explain it", "Longer, with detail."]

    async def test_the_files_of_the_question_come_with_it(self, make_services: Any) -> None:
        """Rewording a question about a file must not quietly drop the file."""
        provider = FakeProvider([text_turn("It contradicts slide 9."), text_turn("Still does.")])
        services = make_services(provider)
        async with _client(services) as client:
            chat_id = await open_chat(client)
            response = await client.post(
                f"{API}/chats/{chat_id}/messages",
                json={
                    "text": "what is wrong here?",
                    "attachments": [{"name": "notes.md", "text": "Slide 14.", "bytes": 9}],
                },
            )
            sse(response)
            asked = _first_user(await _detail(client, chat_id))

            await _redo(client, chat_id, asked["id"], "what is wrong with this?")
            detail = await _detail(client, chat_id)

        assert [f["name"] for f in detail["messages"][0]["attachments"]] == ["notes.md"]
        assert any("Slide 14." in m.content for m in provider.requests[1].messages)

    async def test_only_the_turns_after_it_go(self, make_services: Any) -> None:
        """Asking the second question again leaves the first exchange alone."""
        provider = FakeProvider([text_turn("One."), text_turn("Two."), text_turn("Two again.")])
        services = make_services(provider)
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "first")
            await talk(client, chat_id, "second")
            second = (await _detail(client, chat_id))["messages"][2]

            await _redo(client, chat_id, second["id"])
            detail = await _detail(client, chat_id)

        assert [m["content"] for m in detail["messages"]] == [
            "first",
            "One.",
            "second",
            "Two again.",
        ]

    async def test_an_unknown_message_is_a_404(self, make_services: Any) -> None:
        services = make_services(FakeProvider([text_turn("ok")]))
        async with _client(services) as client:
            chat_id = await open_chat(client)
            response = await client.post(
                f"{API}/chats/{chat_id}/messages/{uuid4()}/redo", json={"text": "x"}
            )

        assert response.status_code == 404

    async def test_an_edit_to_nothing_is_refused(self, make_services: Any) -> None:
        services = make_services(FakeProvider([text_turn("ok"), text_turn("ok")]))
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "something")
            asked = _first_user(await _detail(client, chat_id))
            response = await client.post(
                f"{API}/chats/{chat_id}/messages/{asked['id']}/redo", json={"text": "   "}
            )

        assert response.status_code == 422


async def _detail(client: AsyncClient, chat_id: str) -> Any:
    return (await client.get(f"{API}/chats/{chat_id}")).json()


def _first_user(detail: Any) -> Any:
    return next(message for message in detail["messages"] if message["role"] == "user")


async def _redo(
    client: AsyncClient, chat_id: str, message_id: str, text: str | None = None
) -> list[tuple[str, Any]]:
    body = {} if text is None else {"text": text}
    response = await client.post(f"{API}/chats/{chat_id}/messages/{message_id}/redo", json=body)
    assert response.status_code == 200, response.text
    return sse(response)


class TestThePermissionCard:
    async def test_an_ask_stops_the_stream_with_a_card(
        self, make_services: Any, ask_policy: Policy
    ) -> None:
        provider = FakeProvider([tool_turn(tool_call("fs__read_file", {"path": "a"}))])
        services = make_services(provider, StubTools(policy=ask_policy))
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "read a")

        assert names(frames) == [
            "tool_call_started",
            "tool_call_ready",
            "permission_required",
            "turn_closed",
            "done",
        ]
        card = payload(frames, "permission_required")
        assert card["tool"] == "fs__read_file"
        assert card["reason"] == "it writes to disk"
        assert payload(frames, "turn_closed")["reason"] == "awaiting_permission"

    async def test_allowing_resumes_the_same_message(
        self, make_services: Any, ask_policy: Policy
    ) -> None:
        provider = FakeProvider(
            [tool_turn(tool_call("fs__read_file")), text_turn("It said contents.")]
        )
        services = make_services(provider, StubTools(policy=ask_policy))
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "read a")

            response = await client.post(
                f"{API}/chats/{chat_id}/permissions",
                json={"call_ids": ["call_fs__read_file"], "allow": True},
            )
            frames = sse(response)
            detail = (await client.get(f"{API}/chats/{chat_id}")).json()

        assert names(frames) == [
            "permission_decided",
            "tool_result",
            "text_delta",
            "turn_closed",
            "done",
        ]
        # One assistant message, not two: the answer paused and continued.
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][1]["content"] == "It said contents."

    async def test_refusing_tells_the_model_instead_of_hanging(
        self, make_services: Any, ask_policy: Policy
    ) -> None:
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("Understood.")])
        tools = StubTools(policy=ask_policy)
        services = make_services(provider, tools)
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "read a")
            frames = sse(
                await client.post(
                    f"{API}/chats/{chat_id}/permissions",
                    json={"call_ids": ["call_fs__read_file"], "allow": False},
                )
            )

        assert payload(frames, "tool_result")["failure"] == "denied"
        assert tools.dispatched == []

    async def test_always_allow_writes_a_rule_for_that_exact_tool(
        self, make_services: Any, ask_policy: Policy
    ) -> None:
        """A card about fs__write_file answered with "always" must not quietly permit
        fs__delete_file."""
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("done")])
        services = make_services(provider, StubTools(policy=ask_policy))
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "read a")
            await client.post(
                f"{API}/chats/{chat_id}/permissions",
                json={"call_ids": ["call_fs__read_file"], "allow": True, "remember": True},
            )
            rules = (await client.get(f"{API}/permissions")).json()["rules"]

        written = [rule for rule in rules if rule["pattern"] == "fs__read_file"]
        assert written and written[0]["decision"] == "allow"
        assert not [
            rule for rule in rules if rule["pattern"] == "fs__*" and rule["decision"] == "allow"
        ]

    async def test_the_decision_is_recorded_so_a_reload_shows_a_settled_card(
        self, make_services: Any, ask_policy: Policy
    ) -> None:
        provider = FakeProvider([tool_turn(tool_call("fs__read_file")), text_turn("done")])
        services = make_services(provider, StubTools(policy=ask_policy))
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "read a")
            await client.post(
                f"{API}/chats/{chat_id}/permissions",
                json={"call_ids": ["call_fs__read_file"], "allow": True},
            )
            detail = (await client.get(f"{API}/chats/{chat_id}")).json()

        kinds = [event["type"] for event in detail["messages"][1]["events"]]
        assert "permission_decided" in kinds

    async def test_answering_with_no_turn_to_resume_is_a_404(self, make_services: Any) -> None:
        services = make_services(FakeProvider())
        async with _client(services) as client:
            chat_id = await open_chat(client)
            response = await client.post(
                f"{API}/chats/{chat_id}/permissions",
                json={"call_ids": ["nope"], "allow": True},
            )

        assert response.status_code == 404


class TestTheQuestionCard:
    """`hera__ask` over the whole application: the turn suspends, the events persist, and a
    reply resumes the same assistant message with the words as the call's result."""

    async def test_a_question_suspends_the_turn_and_survives_a_reload(
        self, make_services: Any
    ) -> None:
        provider = FakeProvider(
            [tool_turn(tool_call("hera__ask", {"question": "Which deck?", "kind": "unsure"}))]
        )
        services = make_services(provider, StubTools())
        async with _client(services) as client:
            chat_id = await open_chat(client)
            frames = await talk(client, chat_id, "summarise it")
            detail = (await client.get(f"{API}/chats/{chat_id}")).json()

        assert names(frames) == [
            "tool_call_started",
            "tool_call_ready",
            "answer_required",
            "turn_closed",
            "done",
        ]
        card = payload(frames, "answer_required")
        assert card["question"] == "Which deck?"
        assert card["kind"] == "unsure"
        assert payload(frames, "turn_closed")["reason"] == "awaiting_answer"

        # Persisted, so the card is still there after a reload rather than being a live-only
        # artefact of the stream that stopped.
        stored = [event["type"] for event in detail["messages"][1]["events"]]
        assert "answer_required" in stored

    async def test_replying_resumes_the_same_message(self, make_services: Any) -> None:
        provider = FakeProvider(
            [
                tool_turn(tool_call("hera__ask", {"question": "Which deck?"})),
                text_turn("The 2024 one, then."),
            ]
        )
        services = make_services(provider, StubTools())
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "summarise it")

            frames = sse(
                await client.post(
                    f"{API}/chats/{chat_id}/answers",
                    json={"call_id": "call_hera__ask", "text": "The 2024 one."},
                )
            )
            detail = (await client.get(f"{API}/chats/{chat_id}")).json()

        assert names(frames) == [
            "answer_given",
            "tool_result",
            "text_delta",
            "turn_closed",
            "done",
        ]
        # One assistant message, not two: she asked, waited, and carried on.
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][1]["content"] == "The 2024 one, then."

        # And the reply reached the model as the result of its own call.
        sent = provider.requests[1].messages
        assert any("The 2024 one." in str(message.content) for message in sent)

    async def test_an_unasked_call_id_is_a_404(self, make_services: Any) -> None:
        """Otherwise a resumed turn carries a tool result for a call that was never made, and
        the model is handed an answer to a question it did not ask."""
        provider = FakeProvider([tool_turn(tool_call("hera__ask", {"question": "Which?"}))])
        services = make_services(provider, StubTools())
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "go")

            response = await client.post(
                f"{API}/chats/{chat_id}/answers",
                json={"call_id": "call_something_else", "text": "hello"},
            )

        assert response.status_code == 404

    async def test_replying_to_a_chat_that_never_asked_is_a_404(self, make_services: Any) -> None:
        services = make_services(FakeProvider([text_turn("nothing to ask")]), StubTools())
        async with _client(services) as client:
            chat_id = await open_chat(client)

            response = await client.post(
                f"{API}/chats/{chat_id}/answers",
                json={"call_id": "call_hera__ask", "text": "hello"},
            )

        assert response.status_code == 404


class TestWhenTheModelFails:
    async def test_a_dead_provider_closes_the_turn_rather_than_dropping_the_stream(
        self, make_services: Any
    ) -> None:
        """An exception escaping mid-stream is a connection that just stops, which a browser
        cannot tell from a network problem."""
        from hera_providers import ProviderError

        services = make_services(FakeProvider([ProviderError("endpoint unreachable")]))
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "hi")

        assert names(frames) == ["turn_closed", "done"]
        closed = payload(frames, "turn_closed")
        assert closed["reason"] == "failed"
        assert "unreachable" in closed["error"]

    async def test_a_failed_turn_is_still_persisted(self, make_services: Any) -> None:
        from hera_providers import ProviderError

        services = make_services(FakeProvider([ProviderError("nope")]))
        async with _client(services) as client:
            chat_id = await open_chat(client)
            await talk(client, chat_id, "hi")
            detail = (await client.get(f"{API}/chats/{chat_id}")).json()

        assert detail["messages"][1]["events"][-1]["reason"] == "failed"


@asynccontextmanager
async def _client(services: Services) -> AsyncIterator[AsyncClient]:
    """A client for one container, for tests that script their own provider.

    The lifespan is entered around it so ``app.state.services`` is attached, which is what the
    dependency graph reads the container off.
    """
    app = create_app(services.settings, services=services)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://hera.test") as http,
        app.router.lifespan_context(app),
    ):
        yield http


class TestAttachments:
    async def test_a_file_reaches_the_model_and_the_chip_reaches_the_browser(
        self, make_services: Any
    ) -> None:
        """Two different renderings of the same attachment: the model reads the file, and the
        interface gets a name and a size to draw a chip from — no parsing either way."""
        provider = FakeProvider([text_turn("Slide 14 does contradict slide 9.")])
        services = make_services(provider)

        async with _client(services) as client:
            chat_id = await open_chat(client)
            response = await client.post(
                f"{API}/chats/{chat_id}/messages",
                json={
                    "text": "read this",
                    "attachments": [
                        {"name": "notes.md", "text": "slide 14 contradicts slide 9", "bytes": 28}
                    ],
                },
            )
            frames = sse(response)
            detail = (await client.get(f"{API}/chats/{chat_id}")).json()

        sent = provider.requests[0].messages[-1].content
        assert "Attached file: notes.md" in sent
        assert "slide 14 contradicts slide 9" in sent

        user = detail["messages"][0]
        assert user["content"] == "read this", "the stored message is what was typed"
        assert user["attachments"] == [{"name": "notes.md", "bytes": 28, "media_type": ""}]
        assert "slide 14" not in str(user["attachments"]), "contents do not come back"
        assert names(frames)[-1] == "done"

    async def test_a_picture_reaches_the_model_as_a_content_part(self, make_services: Any) -> None:
        """The bytes go on the wire, not a link: the endpoint is usually a local server with no
        route back to the browser that read the file."""
        from hera_providers import ImagePart, TextPart

        url = "data:image/png;base64,iVBORw0KGgo="
        provider = FakeProvider([text_turn("A white square.")])
        services = make_services(provider)

        async with _client(services) as client:
            chat_id = await open_chat(client)
            response = await client.post(
                f"{API}/chats/{chat_id}/messages",
                json={
                    "text": "what is this?",
                    "attachments": [
                        {
                            "name": "shot.png",
                            "data_url": url,
                            "media_type": "image/png",
                            "bytes": 9,
                        }
                    ],
                },
            )
            frames = sse(response)
            detail = (await client.get(f"{API}/chats/{chat_id}")).json()

        content = provider.requests[0].messages[-1].content
        assert isinstance(content, list), "a message with a picture is a list of parts"
        words, picture = content
        assert isinstance(words, TextPart)
        assert isinstance(picture, ImagePart)
        assert picture.url == url
        # Named in the text too, so "the second screenshot" has something to refer to.
        assert "Attached image: shot.png" in words.text

        chip = detail["messages"][0]["attachments"][0]
        assert chip == {"name": "shot.png", "bytes": 9, "media_type": "image/png"}
        assert url not in str(detail), "the bytes do not come back with the conversation"
        assert names(frames)[-1] == "done"

    async def test_a_message_with_no_picture_stays_a_plain_string(self, make_services: Any) -> None:
        """An installation that never attaches one never sends a differently shaped request."""
        provider = FakeProvider([text_turn("ok")])
        services = make_services(provider)

        async with _client(services) as client:
            chat_id = await open_chat(client)
            await client.post(f"{API}/chats/{chat_id}/messages", json={"text": "hello"})

        assert all(isinstance(m.content, str) for m in provider.requests[0].messages)

    @pytest.mark.parametrize(
        ("attachment", "why"),
        [
            (
                {
                    "name": "a.png",
                    "data_url": "data:image/heic;base64,x",
                    "media_type": "image/heic",
                },
                "an image format no endpoint will accept",
            ),
            (
                {"name": "a.png", "data_url": "not-a-data-url", "media_type": "image/png"},
                "a picture that is not a data URL",
            ),
            (
                {
                    "name": "a.png",
                    "text": "x",
                    "data_url": "data:image/png;base64,x",
                    "media_type": "image/png",
                },
                "both a text body and a picture, with no rule for which wins",
            ),
            ({"name": "a.py"}, "an attachment with nothing in it"),
        ],
    )
    async def test_an_attachment_that_is_neither_one_thing_nor_the_other_is_refused(
        self, make_services: Any, attachment: dict[str, Any], why: str
    ) -> None:
        services = make_services(FakeProvider())

        async with _client(services) as client:
            chat_id = await open_chat(client)
            response = await client.post(
                f"{API}/chats/{chat_id}/messages",
                json={"text": "look", "attachments": [attachment]},
            )

        assert response.status_code == 422, why

    async def test_a_file_on_its_own_is_a_fair_question(self, make_services: Any) -> None:
        services = make_services(FakeProvider([text_turn("It looks fine.")]))

        async with _client(services) as client:
            chat_id = await open_chat(client)
            response = await client.post(
                f"{API}/chats/{chat_id}/messages",
                json={"text": "", "attachments": [{"name": "a.py", "text": "x = 1", "bytes": 5}]},
            )

        assert response.status_code == 200

    async def test_an_empty_message_with_no_file_is_refused(self, make_services: Any) -> None:
        services = make_services(FakeProvider())

        async with _client(services) as client:
            chat_id = await open_chat(client)
            response = await client.post(
                f"{API}/chats/{chat_id}/messages", json={"text": "   ", "attachments": []}
            )

        assert response.status_code == 422

    async def test_the_title_ignores_the_attachment(self, make_services: Any) -> None:
        """A sidebar full of file contents is a sidebar you cannot skim."""
        services = make_services(FakeProvider([text_turn("ok")]))

        async with _client(services) as client:
            chat_id = await open_chat(client)
            await client.post(
                f"{API}/chats/{chat_id}/messages",
                json={
                    "text": "Explain Kerberos",
                    "attachments": [{"name": "notes.md", "text": "x" * 400, "bytes": 400}],
                },
            )
            detail = (await client.get(f"{API}/chats/{chat_id}")).json()

        assert detail["chat"]["title"] == "Explain Kerberos"

"""The streaming turn, end to end over HTTP.

This is the test that says the spine works: a message goes in, Server-Sent Events come out in
the right frames, and what was persisted matches what was streamed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from core_support import API, StubTools, WriteSkill, names, payload, sse
from httpx import ASGITransport, AsyncClient

from hera_core.app import create_app
from hera_core.wiring import Services
from hera_permissions import Policy
from hera_providers import FakeProvider, text_turn, thinking_turn, tool_call, tool_turn


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
            "tool_call_ready",
            "tool_result",
            "text_delta",
            "turn_closed",
            "done",
        ]
        assert payload(frames, "tool_result")["text"] == "ran fs__read_file"


class TestThePermissionCard:
    async def test_an_ask_stops_the_stream_with_a_card(
        self, make_services: Any, ask_policy: Policy
    ) -> None:
        provider = FakeProvider([tool_turn(tool_call("fs__read_file", {"path": "a"}))])
        services = make_services(provider, StubTools(policy=ask_policy))
        async with _client(services) as client:
            frames = await talk(client, await open_chat(client), "read a")

        assert names(frames) == [
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

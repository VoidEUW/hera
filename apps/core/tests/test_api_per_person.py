"""What belongs to a person (ADR 28): their mind, their memories, their rules — end to end.

Two people on one instance, through the real routes and a real turn against `FakeProvider`. The
assertions are about what one of them can see of the other, which should be nothing, and about
what the instance decides for both, which should hold for both.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from core_support import API, StubTools, sign_in
from httpx import ASGITransport, AsyncClient

from hera_accounts import Accounts
from hera_core import rulebook
from hera_core.app import create_app
from hera_core.boot import adopt_memories
from hera_core.wiring import Services
from hera_home import memories_dir, user_memories_dir
from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_providers import FakeProvider, text_turn, tool_call, tool_turn


def make_ben(services: Services) -> UUID:
    with services.database.session() as session:
        return Accounts(session).create("ben@hera.test").id


async def as_ben(client: AsyncClient, services: Services) -> UUID:
    ben = make_ben(services)
    client.cookies.clear()
    sign_in(client, services, ben)
    return ben


def system_prompt(provider: FakeProvider) -> str:
    return str(provider.requests[-1].messages[0].content)


class TestTheMind:
    async def test_each_person_edits_their_own(
        self, client: AsyncClient, services: Services
    ) -> None:
        await client.put(f"{API}/mind/tone", json={"text": "Dry as dust."})
        await as_ben(client, services)

        tones = {r["id"]: r["text"] for r in (await client.get(f"{API}/mind")).json()}
        assert "Dry as dust." not in tones["tone"]
        await client.put(f"{API}/mind/tone", json={"text": "Bubbly."})
        assert services.mind.read("tone") != "Bubbly.\n", "the template is untouched"

    async def test_a_shared_region_is_marked_and_is_the_admins(
        self, client: AsyncClient, services: Services
    ) -> None:
        regions = {r["id"]: r for r in (await client.get(f"{API}/mind")).json()}
        assert regions["safety"]["shared"] is True
        assert regions["tone"]["shared"] is False

        # The admin's edit lands in the template, and so is everybody's.
        edited = await client.put(f"{API}/mind/safety", json={"text": "Never share a key."})
        assert edited.status_code == 200
        assert services.mind.read("safety") == "Never share a key.\n"

        await as_ben(client, services)
        regions = {r["id"]: r for r in (await client.get(f"{API}/mind")).json()}
        assert regions["safety"]["text"] == "Never share a key.\n"
        refused = await client.put(f"{API}/mind/safety", json={"text": "Share everything."})
        assert refused.status_code == 403

    async def test_an_admin_edits_the_template_for_people_yet_to_come(
        self, client: AsyncClient, services: Services
    ) -> None:
        await client.put(f"{API}/mind/tone?scope=template", json={"text": "Warm."})
        template = {r["id"]: r for r in (await client.get(f"{API}/mind?scope=template")).json()}
        assert template["tone"]["text"] == "Warm.\n"

        # Somebody whose mind is made after the change starts from it.
        await as_ben(client, services)
        mine = {r["id"]: r for r in (await client.get(f"{API}/mind")).json()}
        assert mine["tone"]["text"] == "Warm.\n"

    async def test_a_turn_speaks_from_its_owners_mind(
        self, make_services: Any, tmp_path: Path
    ) -> None:
        provider = FakeProvider([text_turn("hello"), text_turn("hello")])
        services: Services = make_services(provider)
        app = create_app(
            services.settings.model_copy(update={"static_dir": str(tmp_path / "x")}),
            services=services,
        )
        async with (
            AsyncClient(transport=ASGITransport(app=app), base_url="http://hera.test") as client,
            app.router.lifespan_context(app),
        ):
            sign_in(client, services)
            await client.put(f"{API}/mind/tone", json={"text": "Speak like a pirate."})
            chat = (await client.post(f"{API}/chats", json={})).json()["id"]
            await client.post(f"{API}/chats/{chat}/messages", json={"text": "hi"})
            assert "Speak like a pirate." in system_prompt(provider)

            await as_ben(client, services)
            chat = (await client.post(f"{API}/chats", json={})).json()["id"]
            await client.post(f"{API}/chats/{chat}/messages", json={"text": "hi"})
            assert "Speak like a pirate." not in system_prompt(provider)


class TestMemories:
    async def test_one_persons_memories_are_not_in_anothers_list_or_prompt(
        self, client: AsyncClient, services: Services
    ) -> None:
        services.for_user(services.settings.owner_id).memories.write("likes-tea", "Tea.")
        assert len((await client.get(f"{API}/memories")).json()) == 1

        ben = await as_ben(client, services)
        assert (await client.get(f"{API}/memories")).json() == []
        assert (await client.delete(f"{API}/memories/likes-tea")).status_code == 404
        assert services.for_user(ben).memories.recall() == ""

    def test_an_install_from_before_accounts_keeps_its_memories(self, tmp_path: Path) -> None:
        legacy = memories_dir()
        legacy.mkdir(parents=True)
        (legacy / "likes-tea.md").write_text("---\ndescription: t\n---\nTea.\n")
        owner = UUID(int=7)

        adopt_memories(owner)
        (legacy / "added-later.md").write_text("x")
        adopt_memories(owner)

        copied = sorted(p.name for p in user_memories_dir(str(owner)).iterdir())
        assert copied == ["likes-tea.md"], "copied once, not again"
        assert (legacy / "likes-tea.md").is_file(), "and nothing deleted"


class TestPermissions:
    @pytest.fixture
    def asking(self) -> Policy:
        return Policy(
            base=PermissionSet(
                rules=[
                    Rule(pattern="fs__*", decision=Decision.ASK),
                    Rule(pattern="shell__*", decision=Decision.DENY),
                ]
            ),
            fallback=Decision.ALLOW,
        )

    async def test_a_persons_own_allow_settles_the_card_for_them_alone(
        self, make_services: Any, asking: Policy, tmp_path: Path
    ) -> None:
        reading = [tool_turn(tool_call("fs__read_file")), text_turn("done")]
        provider = FakeProvider([*reading, *reading])
        tools = StubTools(tools=("fs__read_file",), policy=asking)
        services: Services = make_services(provider, tools)
        rulebook.remember(services.settings.owner_id, ["fs__read_file"], allow=True)
        app = create_app(
            services.settings.model_copy(update={"static_dir": str(tmp_path / "x")}),
            services=services,
        )
        async with (
            AsyncClient(transport=ASGITransport(app=app), base_url="http://hera.test") as client,
            app.router.lifespan_context(app),
        ):
            sign_in(client, services)
            chat = (await client.post(f"{API}/chats", json={})).json()["id"]
            said = (await client.post(f"{API}/chats/{chat}/messages", json={"text": "a"})).text
            assert "permission_required" not in said
            assert len(tools.dispatched) == 1

            await as_ben(client, services)
            chat = (await client.post(f"{API}/chats", json={})).json()["id"]
            said = (await client.post(f"{API}/chats/{chat}/messages", json={"text": "a"})).text
            assert "permission_required" in said
            assert len(tools.dispatched) == 1

    def test_an_always_never_loosens_an_instance_deny(
        self, make_services: Any, asking: Policy
    ) -> None:
        services: Services = make_services(None, StubTools(tools=("shell__run",), policy=asking))
        rulebook.remember(services.settings.owner_id, ["shell__run"], allow=True)
        tools = services.tools_for(services.settings.owner_id)
        assert tools is not None
        assert tools.check("shell__run").decision is Decision.DENY


def test_a_persons_pieces_are_built_once_however_many_ask(services: Services) -> None:
    from concurrent.futures import ThreadPoolExecutor

    ben = make_ben(services)
    with ThreadPoolExecutor(max_workers=8) as pool:
        people = list(pool.map(lambda _: services.for_user(ben), range(8)))

    assert all(person is people[0] for person in people)

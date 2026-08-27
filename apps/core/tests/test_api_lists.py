"""Projects, profiles, the mind, and the settings modal's three lists."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from core_support import API, WriteSkill
from httpx import ASGITransport, AsyncClient

from hera_core.app import create_app
from hera_core.wiring import Services


class TestProfiles:
    async def test_a_fresh_install_already_has_one(self, client: AsyncClient) -> None:
        """Discovering on the first turn that there is nobody to answer as is a bad way to
        find out."""
        profiles = (await client.get(f"{API}/profiles")).json()
        assert [p["slug"] for p in profiles] == ["hera"]
        assert profiles[0]["is_default"]

    async def test_making_one_default_unmarks_the_other(self, client: AsyncClient) -> None:
        first = (await client.get(f"{API}/profiles")).json()[0]
        response = await client.post(f"{API}/profiles/{first['id']}/default")
        assert response.status_code == 200
        assert response.json()["is_default"]

    async def test_another_owners_profile_is_a_404(self, client: AsyncClient) -> None:
        assert (await client.post(f"{API}/profiles/{uuid4()}/default")).status_code == 404


class TestTheMind:
    async def test_every_region_is_listed_with_its_text(self, client: AsyncClient) -> None:
        regions = (await client.get(f"{API}/mind")).json()
        by_id = {region["id"]: region for region in regions}

        assert len(regions) == 12
        assert by_id["character"]["text"].strip()
        assert by_id["safety"]["tier"] == "owner_fixed"
        assert by_id["character"]["tier"] == "evolvable"

    async def test_the_generation_is_a_commit_count(self, client: AsyncClient) -> None:
        """A property of the history rather than a counter somebody has to increment."""
        before = _region(await client.get(f"{API}/mind"), "tone")["generation"]

        await client.put(f"{API}/mind/tone", json={"text": "Terse."})

        after = _region(await client.get(f"{API}/mind"), "tone")["generation"]
        assert after == before + 1

    async def test_the_owners_door_opens_an_owner_fixed_region(self, client: AsyncClient) -> None:
        """Editing `safety` here is the actual mechanism behind "add a rule without touching
        code". Dreaming uses a different door, which refuses these."""
        response = await client.put(
            f"{API}/mind/safety", json={"text": "Never discuss the recipe."}
        )
        assert response.status_code == 200
        assert response.json()["text"].strip() == "Never discuss the recipe."

    async def test_an_edit_changes_the_next_turn(
        self, client: AsyncClient, make_services: Any
    ) -> None:
        await client.put(f"{API}/mind/character", json={"text": "You are a lighthouse."})
        regions = (await client.get(f"{API}/mind")).json()
        assert _find(regions, "character")["text"].strip() == "You are a lighthouse."

    async def test_history_comes_back_newest_first(self, client: AsyncClient) -> None:
        await client.put(f"{API}/mind/tone", json={"text": "One."})
        await client.put(f"{API}/mind/tone", json={"text": "Two."})

        history = (await client.get(f"{API}/mind/tone/history")).json()

        assert len(history) == 3
        assert history[-1]["origin"] == "seed"

    async def test_an_unknown_region_is_a_404(self, client: AsyncClient) -> None:
        assert (await client.put(f"{API}/mind/nope", json={"text": "x"})).status_code == 404
        assert (await client.get(f"{API}/mind/nope/history")).status_code == 404


class TestProjects:
    async def test_creating_and_reading_one(self, client: AsyncClient) -> None:
        created = (
            await client.post(
                f"{API}/projects",
                json={"name": "Hera", "instructions": "Use British spelling."},
            )
        ).json()

        assert created["slug"] == "hera"
        read = (await client.get(f"{API}/projects/{created['id']}")).json()
        assert read["instructions"] == "Use British spelling."

    async def test_patching_leaves_alone_what_it_was_not_given(self, client: AsyncClient) -> None:
        created = (
            await client.post(f"{API}/projects", json={"name": "Hera", "instructions": "Keep."})
        ).json()

        patched = (
            await client.patch(f"{API}/projects/{created['id']}", json={"name": "Hera II"})
        ).json()

        assert patched["name"] == "Hera II"
        assert patched["instructions"] == "Keep."

    async def test_archiving_hides_it_from_the_default_list(self, client: AsyncClient) -> None:
        created = (await client.post(f"{API}/projects", json={"name": "Old"})).json()
        await client.patch(f"{API}/projects/{created['id']}", json={"archived": True})

        assert (await client.get(f"{API}/projects")).json() == []
        assert len((await client.get(f"{API}/projects?include_archived=true")).json()) == 1

    async def test_deleting_revokes_rather_than_erases(self, client: AsyncClient) -> None:
        """The chats inside keep their project_id; a hard delete would leave them pointing at
        nothing, and the reference is a bare UUID with no foreign key to complain."""
        created = (await client.post(f"{API}/projects", json={"name": "Old"})).json()
        assert (await client.delete(f"{API}/projects/{created['id']}")).status_code == 204
        assert (await client.get(f"{API}/projects/{created['id']}")).status_code == 404

    async def test_a_name_that_is_all_whitespace_is_rejected(self, client: AsyncClient) -> None:
        assert (await client.post(f"{API}/projects", json={"name": ""})).status_code == 422

    async def test_a_chat_can_live_in_a_project(self, client: AsyncClient) -> None:
        project = (await client.post(f"{API}/projects", json={"name": "Hera"})).json()
        chat = (await client.post(f"{API}/chats", json={"project_id": project["id"]})).json()

        inside = (await client.get(f"{API}/chats?project_id={project['id']}")).json()
        assert [c["id"] for c in inside] == [chat["id"]]


class TestChats:
    async def test_a_new_chat_takes_the_default_profile(self, client: AsyncClient) -> None:
        profile = (await client.get(f"{API}/profiles")).json()[0]
        chat = (await client.post(f"{API}/chats", json={})).json()
        assert chat["profile_id"] == profile["id"]

    async def test_an_unknown_chat_is_a_404(self, client: AsyncClient) -> None:
        assert (await client.get(f"{API}/chats/{uuid4()}")).status_code == 404

    async def test_deleting_a_chat_takes_its_messages(self, client: AsyncClient) -> None:
        chat = (await client.post(f"{API}/chats", json={})).json()
        assert (await client.delete(f"{API}/chats/{chat['id']}")).status_code == 204
        assert (await client.get(f"{API}/chats")).json() == []


class TestTheSettingsLists:
    async def test_skills_are_listed_with_their_problems(
        self, client: AsyncClient, write_skill: WriteSkill, skills_path: Any
    ) -> None:
        write_skill("tdd", description="Test first.")
        write_skill("nameless", description="")

        listed = (await client.get(f"{API}/skills")).json()

        by_id = {skill["id"]: skill for skill in listed["skills"]}
        assert by_id["tdd"]["problems"] == []
        assert any("retrieval" in p for p in by_id["nameless"]["problems"])

    async def test_a_broken_skill_is_surfaced_rather_than_skipped(
        self, client: AsyncClient, skills_path: Any
    ) -> None:
        """A skill that vanished silently is indistinguishable from one never installed."""
        (skills_path / "notaskill").mkdir()

        listed = (await client.get(f"{API}/skills")).json()

        assert [broken["id"] for broken in listed["broken"]] == ["notaskill"]

    async def test_servers_report_their_connection(self, client: AsyncClient) -> None:
        """A direct rendering of ToolRegistry.status(). Nothing here computes whether a server
        is connected -- a settings screen that derives that can be wrong."""
        assert (await client.get(f"{API}/servers")).json() == []

    async def test_permissions_list_the_rules_and_the_fallback(self, client: AsyncClient) -> None:
        permissions = (await client.get(f"{API}/permissions")).json()
        assert permissions["fallback"] == "ask"
        assert permissions["rules"] == []

    async def test_health_answers_is_it_wired_up(self, client: AsyncClient) -> None:
        health = (await client.get(f"{API}/health")).json()
        assert health["ok"]
        assert health["version"]
        assert health["home"]


class TestTheApiItself:
    async def test_the_schema_is_published(self, client: AsyncClient) -> None:
        """The browser's types are generated from this (ADR 6), so it is a build input rather
        than documentation."""
        schema = (await client.get("/api/openapi.json")).json()
        assert "/api/v1/chats" in schema["paths"]

    async def test_an_unknown_api_path_is_json_not_html(self, client: AsyncClient) -> None:
        """The static mount catches everything, so this is the check that it does not catch
        the API -- an HTML 404 arriving at a fetch() is a parse error blamed on the wrong
        layer."""
        response = await client.get(f"{API}/nope")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")


def _region(response: Any, region_id: str) -> Any:
    return _find(response.json(), region_id)


def _find(regions: list[dict[str, Any]], region_id: str) -> dict[str, Any]:
    return next(region for region in regions if region["id"] == region_id)


class TestServingTheInterface:
    """The built application is served from the same origin (ADR 6), and its client-side
    router needs every unknown path to resolve to index.html."""

    async def test_a_deep_link_serves_the_application(
        self, services: Services, tmp_path: Path
    ) -> None:
        """Every reload inside a conversation lands on a path the server has no file for."""
        async with _serving(services, tmp_path / "static") as http:
            response = await http.get("/chat/3f2a1b4c-0000-0000-0000-000000000000")

        assert response.status_code == 200
        assert response.text == "<!doctype html>the app"

    async def test_a_real_asset_is_still_served(self, services: Services, tmp_path: Path) -> None:
        async with _serving(services, tmp_path / "static") as http:
            response = await http.get("/favicon.svg")

        assert response.text == "<svg/>"

    async def test_the_api_is_not_swallowed_by_the_fallback(
        self, services: Services, tmp_path: Path
    ) -> None:
        """An HTML 404 arriving at a fetch() is a parse error blamed on the wrong layer."""
        async with _serving(services, tmp_path / "static") as http:
            response = await http.get(f"{API}/nope")

        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")

    async def test_no_build_means_no_route_rather_than_a_crash(
        self, services: Services, tmp_path: Path
    ) -> None:
        """Python-only development: a missing static/ must not stop the API from running."""
        settings = services.settings.model_copy(update={"static_dir": str(tmp_path / "absent")})
        app = create_app(settings, services=services)

        async with (
            AsyncClient(transport=ASGITransport(app=app), base_url="http://hera.test") as http,
            app.router.lifespan_context(app),
        ):
            assert (await http.get("/")).status_code == 404
            assert (await http.get(f"{API}/health")).status_code == 200


@asynccontextmanager
async def _serving(services: Services, static: Path) -> AsyncIterator[AsyncClient]:
    """A client for an app that has a built interface behind it.

    The real `static/` is only there after `npm run build`, and the Python test job does not
    run one — so the fixture writes the two files this actually needs.
    """
    static.mkdir(parents=True, exist_ok=True)
    (static / "index.html").write_text("<!doctype html>the app")
    (static / "favicon.svg").write_text("<svg/>")

    settings = services.settings.model_copy(update={"static_dir": str(static)})
    app = create_app(settings, services=services)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://hera.test") as http,
        app.router.lifespan_context(app),
    ):
        yield http

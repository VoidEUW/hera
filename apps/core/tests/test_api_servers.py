"""Settings → Servers: Hera's own server as a box, a server's tools, and adding one (#108).

A real registry over a real stdio subprocess, because what is worth checking is what a person
would: the box appears and connects, a tool unchecked stops being offered, and the file on disk
says what the form said without ever gaining a secret.
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from core_support import API, sign_in
from httpx import ASGITransport, AsyncClient
from mcp.server.mcpserver import MCPServer

from hera_core import permission_rules
from hera_core.app import create_app
from hera_core.wiring import Services
from hera_home import mcp_path
from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_tools import ToolRegistry, ToolsSettings

SHIPPED = Policy(
    base=PermissionSet(
        rules=[Rule(pattern="hera__*", decision=Decision.ALLOW, reason="her own tools")]
    ),
    fallback=Decision.ALLOW,
)

STDIO = """
from mcp.server.mcpserver import MCPServer

server = MCPServer("spike", version="0.1.0")


@server.tool(description="Repeat the text back.")
def echo(text: str) -> str:
    return "echo:" + text


@server.tool(description="Say hello.")
def hello() -> str:
    return "hello"


server.run(transport="stdio")
"""


def entry(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"kind": "stdio", "command": sys.executable, "args": ["-c", STDIO]}
    return {**body, **over}


def built_in() -> MCPServer:
    server: MCPServer = MCPServer("hera", version="0.1.0")

    @server.tool(description="Write a note.")
    def note(text: str) -> str:
        return "written"

    return server


@asynccontextmanager
async def serving(make_services: Any) -> AsyncIterator[tuple[AsyncClient, Services]]:
    registry = ToolRegistry.open(
        policy=SHIPPED,
        settings=ToolsSettings(retry_after_s=0.0, startup_timeout_s=20.0),
        builtin=built_in(),
    )
    services: Services = make_services(registry=registry)
    services.default_policy = SHIPPED
    app = create_app(services.settings, services=services)
    try:
        async with (
            AsyncClient(transport=ASGITransport(app=app), base_url="http://hera.test") as http,
            app.router.lifespan_context(app),
        ):
            yield sign_in(http, services), services
    finally:
        assert services.registry is not None
        await services.registry.aclose()


def written() -> dict[str, Any]:
    return dict(json.loads(mcp_path().read_text(encoding="utf-8")))


class TestListing:
    async def test_her_own_server_is_listed_first_and_flagged(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            servers = (await http.get(f"{API}/servers")).json()

        assert [(s["name"], s["builtin"], s["kind"]) for s in servers] == [
            ("hera", True, "builtin")
        ]
        assert servers[0]["tools"] == 1

    async def test_a_server_that_is_switched_off_is_still_a_box(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            await http.put(f"{API}/servers/spike", json=entry(enabled=False))
            servers = (await http.get(f"{API}/servers")).json()

        spike = next(s for s in servers if s["name"] == "spike")
        assert (spike["enabled"], spike["connected"], spike["tools"]) == (False, False, 0)

    async def test_the_health_card_still_counts_only_the_ones_a_person_added(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, _):
            assert (await http.get(f"{API}/health")).json()["servers"] == []
            await http.put(f"{API}/servers/spike", json=entry())
            names = [s["name"] for s in (await http.get(f"{API}/health")).json()["servers"]]

        assert names == ["spike"]

    async def test_no_tool_layer_lists_nothing(self, services: Services, app: Any) -> None:
        async with (
            AsyncClient(transport=ASGITransport(app=app), base_url="http://hera.test") as http,
            app.router.lifespan_context(app),
        ):
            sign_in(http, services)
            assert (await http.get(f"{API}/servers")).json() == []
            assert (await http.put(f"{API}/servers/x", json=entry())).status_code == 409


class TestAdding:
    async def test_a_new_server_connects_and_lands_in_the_file(self, make_services: Any) -> None:
        async with serving(make_services) as (http, services):
            response = await http.put(f"{API}/servers/spike", json=entry())
            servers = (await http.get(f"{API}/servers")).json()

        assert response.status_code == 201
        spike = next(s for s in servers if s["name"] == "spike")
        assert (spike["connected"], spike["tools"], spike["kind"]) == (True, 2, "stdio")
        assert written()["mcpServers"]["spike"]["command"] == sys.executable
        assert services.orchestrator.registry is services.registry

    async def test_saving_it_again_is_a_replace_and_leaves_the_others_connected(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, services):
            await http.put(f"{API}/servers/spike", json=entry())
            await http.put(f"{API}/servers/other", json=entry())
            before = {s.name: s for s in services.registry._servers}  # type: ignore[union-attr]

            response = await http.put(f"{API}/servers/other", json=entry(args=["-c", STDIO, "x"]))
            after = {s.name: s for s in services.registry._servers}  # type: ignore[union-attr]

        assert response.status_code == 200
        assert after["spike"] is before["spike"]
        assert after["hera"] is before["hera"]
        assert after["other"] is not before["other"]

    async def test_a_bad_entry_is_refused_and_the_file_is_untouched(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, _):
            neither = await http.put(f"{API}/servers/bad", json=entry(command=""))
            named = await http.put(f"{API}/servers/two__parts", json=entry())
            unset = await http.put(
                f"{API}/servers/bad", json=entry(env={"A": "${HERA_UNSET_FOR_THE_TEST}"})
            )

        assert [r.status_code for r in (neither, named, unset)] == [422, 422, 422]
        assert not mcp_path().exists()

    async def test_her_own_server_cannot_be_written_or_deleted(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            put = await http.put(f"{API}/servers/hera", json=entry())
            gone = await http.delete(f"{API}/servers/hera")

        assert (put.status_code, gone.status_code) == (409, 409)

    async def test_a_file_nobody_can_parse_is_not_written_over(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            # Broken after boot, by hand: the start would have refused it.
            mcp_path().parent.mkdir(parents=True, exist_ok=True)
            mcp_path().write_text("{ not json", encoding="utf-8")
            response = await http.put(f"{API}/servers/spike", json=entry())
            listed = await http.get(f"{API}/servers")

        assert response.status_code == 422
        assert listed.status_code == 200
        assert mcp_path().read_text(encoding="utf-8") == "{ not json"


class TestSecrets:
    async def test_a_literal_secret_never_leaves_and_is_kept_when_sent_back_hidden(
        self, make_services: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERA_TEST_TOKEN", "from-the-environment")
        async with serving(make_services) as (http, _):
            await http.put(
                f"{API}/servers/spike",
                json=entry(env={"LITERAL": "hunter2", "REF": "${HERA_TEST_TOKEN}"}),
            )
            shown = (await http.get(f"{API}/servers/spike/config")).json()
            await http.put(
                f"{API}/servers/spike",
                json=entry(env={"LITERAL": None, "REF": "${HERA_TEST_TOKEN}"}),
            )

        assert shown["env"] == {"LITERAL": None, "REF": "${HERA_TEST_TOKEN}"}
        assert "hunter2" not in json.dumps(shown)
        on_disk = written()["mcpServers"]["spike"]["env"]
        assert on_disk == {"LITERAL": "hunter2", "REF": "${HERA_TEST_TOKEN}"}
        assert "from-the-environment" not in mcp_path().read_text(encoding="utf-8")

    async def test_keys_this_client_does_not_read_survive_an_edit(self, make_services: Any) -> None:
        mcp_path().parent.mkdir(parents=True, exist_ok=True)
        mcp_path().write_text(
            json.dumps({"mcpServers": {"spike": {**_raw(), "alwaysAllow": ["echo"]}}}),
            encoding="utf-8",
        )
        async with serving(make_services) as (http, _):
            await http.put(f"{API}/servers/spike", json=entry(enabled=True))

        assert written()["mcpServers"]["spike"]["alwaysAllow"] == ["echo"]

    async def test_reading_a_server_that_is_not_there(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            assert (await http.get(f"{API}/servers/nope/config")).status_code == 404


def _raw() -> dict[str, Any]:
    return {"command": sys.executable, "args": ["-c", STDIO]}


class TestRemoving:
    async def test_it_is_gone_from_the_file_and_the_registry(self, make_services: Any) -> None:
        async with serving(make_services) as (http, services):
            await http.put(f"{API}/servers/spike", json=entry())
            gone = await http.delete(f"{API}/servers/spike")
            again = await http.delete(f"{API}/servers/spike")
            servers = (await http.get(f"{API}/servers")).json()

        assert (gone.status_code, again.status_code) == (204, 404)
        assert written()["mcpServers"] == {}
        assert [s["name"] for s in servers] == ["hera"]
        assert services.orchestrator.registry is services.registry


class TestTools:
    async def test_a_servers_tools_are_listed_with_their_descriptions_and_state(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, _):
            await http.put(f"{API}/servers/spike", json=entry())
            tools = (await http.get(f"{API}/servers/spike/tools")).json()

        assert [(t["name"], t["description"], t["allowed"]) for t in tools] == [
            ("spike__echo", "Repeat the text back.", True),
            ("spike__hello", "Say hello.", True),
        ]

    async def test_hers_are_listed_like_any_other(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            tools = (await http.get(f"{API}/servers/hera/tools")).json()

        assert [t["name"] for t in tools] == ["hera__note"]

    async def test_a_server_nobody_has_is_a_404(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            assert (await http.get(f"{API}/servers/nope/tools")).status_code == 404

    async def test_unchecking_writes_a_deny_rule_she_is_not_offered_and_keeps_it(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, services):
            await http.put(f"{API}/servers/spike", json=entry())
            off = await http.put(f"{API}/servers/spike/tools/echo", json={"allowed": False})
            rules = (await http.get(f"{API}/permissions")).json()["rules"]
            assert services.registry is not None
            asked = services.registry.check("spike__echo")

        assert off.json()["allowed"] is False
        assert off.json()["exact"] is True
        deny = next(r for r in rules if r["pattern"] == "spike__echo")
        assert (deny["decision"], deny["source"], deny["name"]) == (
            "deny",
            "you",
            "Off on the Servers screen",
        )
        assert asked.decision is Decision.DENY
        assert permission_rules.load().get("spike__echo") is not None

    async def test_checking_it_again_takes_the_rule_away(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            await http.put(f"{API}/servers/spike", json=entry())
            await http.put(f"{API}/servers/spike/tools/echo", json={"allowed": False})
            on = await http.put(f"{API}/servers/spike/tools/echo", json={"allowed": True})
            rules = (await http.get(f"{API}/permissions")).json()["rules"]

        assert on.json()["allowed"] is True
        assert all(r["pattern"] != "spike__echo" for r in rules)

    async def test_a_wider_deny_is_beaten_by_an_exact_allow_and_says_what_it_was(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, _):
            await http.put(f"{API}/servers/spike", json=entry())
            await http.post(
                f"{API}/permissions/rules", json={"pattern": "spike__*", "decision": "deny"}
            )
            listed = (await http.get(f"{API}/servers/spike/tools")).json()
            on = await http.put(f"{API}/servers/spike/tools/echo", json={"allowed": True})
            after = (await http.get(f"{API}/servers/spike/tools")).json()

        assert [(t["allowed"], t["rule"], t["exact"]) for t in listed] == [
            (False, "spike__*", False),
            (False, "spike__*", False),
        ]
        assert on.json()["allowed"] is True
        assert [t["allowed"] for t in after] == [True, False]

    async def test_an_answered_always_is_turned_off_rather_than_left_as_it_was(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, _):
            await http.put(f"{API}/servers/spike", json=entry())
            await http.post(
                f"{API}/permissions/rules", json={"pattern": "spike__echo", "decision": "allow"}
            )
            off = await http.put(f"{API}/servers/spike/tools/echo", json={"allowed": False})

        assert off.json()["allowed"] is False

    async def test_a_tool_the_server_does_not_have(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            await http.put(f"{API}/servers/spike", json=entry())
            response = await http.put(f"{API}/servers/spike/tools/nope", json={"allowed": False})

        assert response.status_code == 404

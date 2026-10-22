"""Settings → Permissions: rules a person can make, change and remove, and keep (#109).

What is worth asserting is what a person would check by hand: the rule appears, the tool layer is
actually asking it, and it is still there after a restart — which here means a fresh policy built
from what is on disk.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from core_support import API, StubTools
from httpx import ASGITransport, AsyncClient

from hera_core import permission_rules
from hera_core.app import create_app
from hera_core.wiring import DEFAULT_POLICY, Services
from hera_home import permissions_path
from hera_permissions import Decision, PermissionSet, Policy, Rule

SHIPPED = Policy(
    base=PermissionSet(
        rules=[Rule(pattern="hera__*", decision=Decision.ALLOW, reason="her own tools")]
    ),
    fallback=Decision.ASK,
)


@asynccontextmanager
async def serving(
    make_services: Any, *, tools: tuple[str, ...] = ("fs__read_file", "fs__write_file")
) -> AsyncIterator[tuple[AsyncClient, Services]]:
    services: Services = make_services(registry=StubTools(tools=tools, policy=SHIPPED))
    services.default_policy = SHIPPED
    app = create_app(services.settings, services=services)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://hera.test") as http,
        app.router.lifespan_context(app),
    ):
        yield http, services


def on_disk() -> dict[str, Any]:
    return dict(json.loads(permissions_path().read_text(encoding="utf-8")))


class TestReading:
    async def test_it_lists_the_shipped_rule_with_where_it_came_from_and_what_it_covers(
        self, make_services: Any
    ) -> None:
        async with serving(make_services, tools=("hera__note", "fs__read_file")) as (http, _):
            body = (await http.get(f"{API}/permissions")).json()

        assert body["fallback"] == "ask"
        [rule] = body["rules"]
        assert (rule["pattern"], rule["decision"], rule["source"]) == (
            "hera__*",
            "allow",
            "default",
        )
        assert rule["covers"] == ["hera__note"]

    async def test_a_deployment_with_no_tool_layer_has_no_rules(
        self, services: Services, app: Any
    ) -> None:
        async with (
            AsyncClient(transport=ASGITransport(app=app), base_url="http://hera.test") as http,
            app.router.lifespan_context(app),
        ):
            body = (await http.get(f"{API}/permissions")).json()

        assert body == {"fallback": "ask", "rules": []}


class TestMaking:
    async def test_a_new_rule_is_listed_enforced_and_written_down(self, make_services: Any) -> None:
        async with serving(make_services) as (http, services):
            response = await http.post(
                f"{API}/permissions/rules",
                json={
                    "name": "Reading files",
                    "pattern": "fs__read*",
                    "decision": "allow",
                    "reason": "reads only",
                },
            )
            listed = (await http.get(f"{API}/permissions")).json()["rules"]

        assert response.status_code == 201
        assert response.json()["covers"] == ["fs__read_file"]
        assert [rule["pattern"] for rule in listed] == ["fs__read*", "hera__*"]
        assert services.registry is not None
        assert services.registry.policy.check("fs__read_file").decision is Decision.ALLOW
        assert services.registry.policy.check("fs__write_file").decision is Decision.ASK
        assert services.orchestrator.registry is services.registry
        assert on_disk()["rules"][0] == {
            "pattern": "fs__read*",
            "decision": "allow",
            "reason": "reads only",
            "name": "Reading files",
            "source": "you",
        }

    async def test_it_comes_back_after_a_restart(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            await http.post(
                f"{API}/permissions/rules", json={"pattern": "fs__write*", "decision": "deny"}
            )

        restarted = permission_rules.apply(SHIPPED, permission_rules.load())

        assert restarted.check("fs__write_file").decision is Decision.DENY
        assert restarted.check("hera__note").decision is Decision.ALLOW

    async def test_a_second_rule_on_the_same_pattern_is_refused_not_replaced(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, services):
            await http.post(
                f"{API}/permissions/rules", json={"pattern": "fs__*", "decision": "ask"}
            )
            again = await http.post(
                f"{API}/permissions/rules", json={"pattern": "fs__*", "decision": "allow"}
            )

        assert again.status_code == 409
        assert services.registry is not None
        assert services.registry.policy.check("fs__read_file").decision is Decision.ASK

    @pytest.mark.parametrize("pattern", ["", "   "])
    async def test_an_empty_pattern_is_refused(self, make_services: Any, pattern: str) -> None:
        async with serving(make_services) as (http, _):
            response = await http.post(
                f"{API}/permissions/rules", json={"pattern": pattern, "decision": "allow"}
            )

        assert response.status_code == 422
        assert not permissions_path().exists()

    async def test_a_decision_that_is_not_one_is_refused(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            response = await http.post(
                f"{API}/permissions/rules", json={"pattern": "fs__*", "decision": "maybe"}
            )

        assert response.status_code == 422


class TestChanging:
    async def test_a_rule_can_be_renamed_and_flipped_but_keeps_its_pattern(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, services):
            await http.post(
                f"{API}/permissions/rules", json={"pattern": "fs__*", "decision": "allow"}
            )
            response = await http.patch(
                f"{API}/permissions/rules/fs__*",
                json={"name": "Files", "decision": "deny", "reason": "not today"},
            )

        assert response.status_code == 200
        assert response.json()["name"] == "Files"
        assert response.json()["pattern"] == "fs__*"
        assert services.registry is not None
        assert services.registry.policy.check("fs__read_file").decision is Decision.DENY
        assert on_disk()["rules"][0]["reason"] == "not today"

    async def test_only_what_is_sent_changes(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            await http.post(
                f"{API}/permissions/rules",
                json={"pattern": "fs__*", "decision": "allow", "name": "Files", "reason": "why"},
            )
            response = await http.patch(f"{API}/permissions/rules/fs__*", json={"name": "Disk"})

        body = response.json()
        assert (body["name"], body["decision"], body["reason"]) == ("Disk", "allow", "why")

    async def test_changing_a_shipped_rule_makes_a_rule_of_your_own_on_that_pattern(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, services):
            response = await http.patch(
                f"{API}/permissions/rules/hera__*", json={"decision": "ask"}
            )

        assert response.json()["source"] == "you"
        assert services.registry is not None
        assert services.registry.policy.check("hera__note").decision is Decision.ASK
        assert on_disk()["rules"][0]["pattern"] == "hera__*"

    async def test_an_unknown_rule_is_a_404(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            response = await http.patch(f"{API}/permissions/rules/nope__*", json={"name": "x"})

        assert response.status_code == 404

    async def test_a_pattern_with_a_bracket_and_a_question_mark_is_addressable(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, _):
            await http.post(
                f"{API}/permissions/rules", json={"pattern": "fs__[rw]?", "decision": "ask"}
            )
            response = await http.patch(
                f"{API}/permissions/rules/fs__%5Brw%5D%3F", json={"name": "Odd"}
            )

        assert response.status_code == 200


class TestRemoving:
    async def test_deleting_a_rule_hands_its_tools_back_and_forgets_it(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, services):
            await http.post(
                f"{API}/permissions/rules", json={"pattern": "fs__*", "decision": "deny"}
            )
            response = await http.delete(f"{API}/permissions/rules/fs__*")

        assert response.status_code == 204
        assert services.registry is not None
        assert services.registry.policy.check("fs__read_file").decision is Decision.ASK
        assert on_disk()["rules"] == []

    async def test_a_shipped_rule_cannot_be_deleted(self, make_services: Any) -> None:
        async with serving(make_services) as (http, services):
            response = await http.delete(f"{API}/permissions/rules/hera__*")

        assert response.status_code == 409
        assert services.registry is not None
        assert services.registry.policy.check("hera__note").decision is Decision.ALLOW

    async def test_deleting_an_override_puts_the_shipped_rule_back(
        self, make_services: Any
    ) -> None:
        async with serving(make_services) as (http, services):
            await http.patch(f"{API}/permissions/rules/hera__*", json={"decision": "deny"})
            await http.delete(f"{API}/permissions/rules/hera__*")
            listed = (await http.get(f"{API}/permissions")).json()["rules"]

        assert services.registry is not None
        assert services.registry.policy.check("hera__note").decision is Decision.ALLOW
        assert listed[0]["source"] == "default"

    async def test_an_unknown_rule_is_a_404(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            response = await http.delete(f"{API}/permissions/rules/nope__*")

        assert response.status_code == 404


class TestTheFallback:
    async def test_it_can_be_changed_and_is_kept(self, make_services: Any) -> None:
        async with serving(make_services) as (http, services):
            response = await http.patch(f"{API}/permissions", json={"fallback": "deny"})

        assert response.json()["fallback"] == "deny"
        assert services.registry is not None
        assert services.registry.policy.check("other__tool").decision is Decision.DENY
        assert on_disk()["fallback"] == "deny"

    async def test_setting_it_back_to_the_shipped_one_forgets_the_choice(
        self, make_services: Any
    ) -> None:
        """So a better default later still reaches this install."""
        async with serving(make_services) as (http, _):
            await http.patch(f"{API}/permissions", json={"fallback": "deny"})
            await http.patch(f"{API}/permissions", json={"fallback": "ask"})

        assert on_disk()["fallback"] is None


class TestPreview:
    async def test_it_says_which_tools_a_pattern_would_cover(self, make_services: Any) -> None:
        async with serving(make_services, tools=("fs__read_file", "git__log")) as (http, _):
            body = (
                await http.get(f"{API}/permissions/matches", params={"pattern": "fs__*"})
            ).json()

        assert body == {"pattern": "fs__*", "tools": ["fs__read_file"]}

    async def test_a_pattern_that_covers_nothing_says_so(self, make_services: Any) -> None:
        async with serving(make_services) as (http, _):
            body = (
                await http.get(f"{API}/permissions/matches", params={"pattern": "zz__*"})
            ).json()

        assert body["tools"] == []


class TestTheFile:
    def test_nothing_there_is_an_empty_set(self) -> None:
        assert permission_rules.load() == permission_rules.StoredPermissions()

    def test_a_file_that_cannot_be_used_is_said_aloud_and_left_alone(self) -> None:
        path = permissions_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")

        with pytest.raises(permission_rules.PermissionsFileError, match=r"permissions\.json"):
            permission_rules.load()

        assert path.read_text(encoding="utf-8") == "{not json"

    def test_a_rule_with_a_decision_that_is_not_one_is_not_silently_dropped(self) -> None:
        path = permissions_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"rules": [{"pattern": "fs__*", "decision": "maybe"}]}), encoding="utf-8"
        )

        with pytest.raises(permission_rules.PermissionsFileError):
            permission_rules.load()

    def test_it_is_written_sorted_and_without_a_leftover_temporary(self, tmp_path: Path) -> None:
        stored = permission_rules.StoredPermissions(
            rules=[
                permission_rules.StoredRule(pattern="b__*", decision=Decision.ALLOW),
                permission_rules.StoredRule(pattern="a__*", decision=Decision.DENY),
            ]
        )
        target = tmp_path / "permissions.json"

        permission_rules.save(stored, target)

        assert [rule["pattern"] for rule in json.loads(target.read_text())["rules"]] == [
            "a__*",
            "b__*",
        ]
        assert list(tmp_path.iterdir()) == [target]

    def test_the_default_policy_is_what_a_fresh_install_runs(self) -> None:
        assert permission_rules.apply(DEFAULT_POLICY, permission_rules.StoredPermissions()) == (
            DEFAULT_POLICY
        )


class TestAnsweringAlways:
    """The card's "always" and this screen are one mechanism (#109): the rule survives."""

    async def test_it_is_written_named_and_marked_as_coming_from_a_card(
        self, make_services: Any
    ) -> None:
        from hera_core import rulebook

        async with serving(make_services) as (http, services):
            rulebook.remember(services, ["fs__read_file"], allow=True)
            listed = (await http.get(f"{API}/permissions")).json()["rules"]

        card = next(rule for rule in listed if rule["pattern"] == "fs__read_file")
        assert card["source"] == "card"
        assert card["name"] == "Allowed from a card · fs read_file"
        assert on_disk()["rules"][0]["source"] == "card"
        restarted = permission_rules.apply(SHIPPED, permission_rules.load())
        assert restarted.check("fs__read_file").decision is Decision.ALLOW

    async def test_a_refusal_is_remembered_too(self, make_services: Any) -> None:
        from hera_core import rulebook

        async with serving(make_services) as (_, services):
            rulebook.remember(services, ["fs__write_file"], allow=False)

        restarted = permission_rules.apply(SHIPPED, permission_rules.load())
        assert restarted.check("fs__write_file").decision is Decision.DENY
        assert on_disk()["rules"][0]["name"] == "Denied from a card · fs write_file"

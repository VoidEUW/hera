"""Signing in and out, registering, sessions, and the lines drawn around them (ADR 27).

Against the real application: the cookie a browser is handed, the 401 a route answers without
one, the 403 a non-admin gets from an instance route, and the Origin check in front of all of it.
"""

from __future__ import annotations

from typing import Any

import pytest
from core_support import API, OWNER_EMAIL, OWNER_PASSWORD, sign_in, unclaim
from httpx import AsyncClient

from hera_accounts import Accounts, Purpose, Role
from hera_core.auth import SESSION_COOKIE, Throttle
from hera_core.config import load as load_config
from hera_core.config import save as save_config
from hera_core.wiring import Services


def make_user(services: Services, email: str, *, role: Role = Role.USER, password: str = "") -> Any:
    with services.database.session() as session:
        return Accounts(session).create(email, role=role, password=password or None).id


def set_registration(mode: str) -> None:
    save_config(load_config().with_instance(registration=mode))


class TestTheLine:
    async def test_a_route_without_a_session_is_a_401(self, anonymous: AsyncClient) -> None:
        for path in ("/chats", "/health", "/providers", "/account", "/instance"):
            assert (await anonymous.get(f"{API}{path}")).status_code == 401, path

    async def test_what_a_stranger_may_ask_is_short(self, anonymous: AsyncClient) -> None:
        assert (await anonymous.get(f"{API}/live")).json() == {"ok": True}
        assert (await anonymous.get(f"{API}/auth/state")).status_code == 200
        assert (await anonymous.get(f"{API}/setup")).status_code == 200

    async def test_a_cookie_that_is_not_a_session_is_a_401(self, anonymous: AsyncClient) -> None:
        anonymous.cookies.set(SESSION_COOKIE, "made-up", domain="hera.test")
        assert (await anonymous.get(f"{API}/chats")).status_code == 401


class TestSigningIn:
    async def test_the_state_says_who_is_signed_in(
        self, anonymous: AsyncClient, client: AsyncClient
    ) -> None:
        # `client` is `anonymous` with a cookie, so ask before it was set by asking a fresh one.
        body = (await client.get(f"{API}/auth/state")).json()
        assert body["user"]["email"] == OWNER_EMAIL
        assert body["setup_required"] is False
        assert body["registration"] == "closed"
        assert body["instance_name"] == "Hera"

    async def test_signing_in_hands_over_an_httponly_lax_cookie(
        self, anonymous: AsyncClient
    ) -> None:
        response = await anonymous.post(
            f"{API}/auth/sign-in", json={"email": OWNER_EMAIL.upper(), "password": OWNER_PASSWORD}
        )

        assert response.status_code == 200
        assert response.json()["role"] == "admin"
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f"{SESSION_COOKIE}=")
        assert "HttpOnly" in cookie
        assert "samesite=lax" in cookie.lower()
        assert "Secure" not in cookie  # plain http here; https gets it
        assert (await anonymous.get(f"{API}/chats")).status_code == 200

    async def test_a_wrong_password_and_an_unknown_email_read_the_same(
        self, anonymous: AsyncClient
    ) -> None:
        wrong = await anonymous.post(
            f"{API}/auth/sign-in", json={"email": OWNER_EMAIL, "password": "not it at all"}
        )
        unknown = await anonymous.post(
            f"{API}/auth/sign-in", json={"email": "nobody@hera.test", "password": "not it at all"}
        )
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json()

    async def test_guessing_is_slowed_down(self, anonymous: AsyncClient) -> None:
        guess = {"email": OWNER_EMAIL, "password": "guess guess"}
        for _ in range(5):
            assert (await anonymous.post(f"{API}/auth/sign-in", json=guess)).status_code == 401
        refused = await anonymous.post(
            f"{API}/auth/sign-in", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}
        )
        assert refused.status_code == 429
        assert int(refused.headers["retry-after"]) >= 1

    async def test_signing_out_ends_the_session_and_the_cookie(
        self, client: AsyncClient, services: Services
    ) -> None:
        response = await client.post(f"{API}/auth/sign-out")
        assert response.status_code == 204
        assert 'hera_session=""' in response.headers["set-cookie"]
        assert (await client.get(f"{API}/chats")).status_code == 401
        with services.database.session() as session:
            assert Accounts(session).sessions(services.settings.owner_id) == []

    async def test_signing_in_again_replaces_the_session_it_carried(
        self, client: AsyncClient, services: Services
    ) -> None:
        await client.post(
            f"{API}/auth/sign-in", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}
        )
        with services.database.session() as session:
            assert len(Accounts(session).sessions(services.settings.owner_id)) == 1

    async def test_a_disabled_account_is_signed_out_at_once(
        self, client: AsyncClient, services: Services
    ) -> None:
        ben = make_user(services, "ben@hera.test")
        sign_in(client, services, ben)
        with services.database.session() as session:
            accounts = Accounts(session)
            user = accounts.get(ben)
            assert user is not None
            accounts.set_disabled(user, True)
        assert (await client.get(f"{API}/chats")).status_code == 401


NEWCOMER = {"name": "Ben", "email": "ben@hera.test", "password": "a long password"}


class TestRegistering:
    async def test_closed_is_the_default(self, anonymous: AsyncClient) -> None:
        response = await anonymous.post(f"{API}/auth/register", json=NEWCOMER)
        assert response.status_code == 403
        assert "closed" in response.json()["detail"]

    async def test_open_makes_a_user_and_signs_them_in(self, anonymous: AsyncClient) -> None:
        set_registration("open")
        response = await anonymous.post(f"{API}/auth/register", json=NEWCOMER)

        assert response.status_code == 201
        assert response.json()["role"] == "user"
        assert (await anonymous.get(f"{API}/account")).json()["email"] == "ben@hera.test"
        # Somebody to be answered as, from the first turn.
        [profile] = (await anonymous.get(f"{API}/profiles")).json()
        assert profile["is_default"] is True
        again = await anonymous.post(f"{API}/auth/register", json=NEWCOMER)
        assert again.status_code == 409

    async def test_a_short_password_is_refused_with_the_reason(
        self, anonymous: AsyncClient
    ) -> None:
        set_registration("open")
        response = await anonymous.post(
            f"{API}/auth/register", json={**NEWCOMER, "password": "short"}
        )
        assert response.status_code == 422
        assert "at least" in response.json()["detail"]

    async def test_invite_needs_a_token_that_works(
        self, anonymous: AsyncClient, services: Services
    ) -> None:
        from datetime import timedelta

        set_registration("invite")
        with services.database.session() as session:
            invite = Accounts(session).issue(Purpose.INVITE, lifetime=timedelta(days=1))

        refused = await anonymous.post(f"{API}/auth/register", json={**NEWCOMER, "invite": "nope"})
        assert refused.status_code == 403
        made = await anonymous.post(f"{API}/auth/register", json={**NEWCOMER, "invite": invite})
        assert made.status_code == 201
        spent = await anonymous.post(
            f"{API}/auth/register",
            json={**NEWCOMER, "email": "cy@hera.test", "invite": invite},
        )
        assert spent.status_code == 403

    async def test_an_unclaimed_instance_is_set_up_not_registered_into(
        self, anonymous: AsyncClient, services: Services
    ) -> None:
        set_registration("open")
        unclaim(services.database)
        response = await anonymous.post(f"{API}/auth/register", json=NEWCOMER)
        assert response.status_code == 409


class TestSessions:
    async def test_the_list_marks_this_browser(
        self, client: AsyncClient, services: Services
    ) -> None:
        with services.database.session() as session:
            Accounts(session).open_session(services.settings.owner_id, user_agent="Phone")

        rows = (await client.get(f"{API}/auth/sessions")).json()

        assert len(rows) == 2
        assert [row["current"] for row in rows].count(True) == 1
        assert {row["user_agent"] for row in rows} >= {"Phone"}

    async def test_another_session_can_be_revoked_and_somebody_elses_cannot(
        self, client: AsyncClient, services: Services
    ) -> None:
        ben = make_user(services, "ben@hera.test")
        with services.database.session() as session:
            accounts = Accounts(session)
            _, phone = accounts.open_session(services.settings.owner_id, user_agent="Phone")
            _, bens = accounts.open_session(ben)
            phone_id, bens_id = phone.id, bens.id

        assert (await client.delete(f"{API}/auth/sessions/{bens_id}")).status_code == 404
        assert (await client.delete(f"{API}/auth/sessions/{phone_id}")).status_code == 204
        assert len((await client.get(f"{API}/auth/sessions")).json()) == 1

    async def test_everywhere_includes_here(self, client: AsyncClient, services: Services) -> None:
        with services.database.session() as session:
            Accounts(session).open_session(services.settings.owner_id)

        assert (await client.delete(f"{API}/auth/sessions")).status_code == 204
        assert (await client.get(f"{API}/chats")).status_code == 401
        with services.database.session() as session:
            assert Accounts(session).sessions(services.settings.owner_id) == []


class TestChangingThePassword:
    async def test_it_needs_the_current_one(self, client: AsyncClient) -> None:
        response = await client.put(
            f"{API}/auth/password", json={"current": "wrong one!", "new": "a new password"}
        )
        assert response.status_code == 403

    async def test_it_signs_out_every_other_browser(
        self, client: AsyncClient, anonymous: AsyncClient, services: Services
    ) -> None:
        with services.database.session() as session:
            Accounts(session).open_session(services.settings.owner_id, user_agent="Phone")

        response = await client.put(
            f"{API}/auth/password", json={"current": OWNER_PASSWORD, "new": "a new password"}
        )

        assert response.status_code == 204
        rows = (await client.get(f"{API}/auth/sessions")).json()
        assert [row["current"] for row in rows] == [True]
        with services.database.session() as session:
            assert Accounts(session).verify(OWNER_EMAIL, "a new password") is not None


class TestTheOriginCheck:
    async def test_a_request_from_another_site_is_refused(self, client: AsyncClient) -> None:
        response = await client.post(
            f"{API}/chats", json={}, headers={"origin": "https://evil.example"}
        )
        assert response.status_code == 403

    async def test_a_cross_site_fetch_is_refused_even_without_an_origin(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            f"{API}/chats", json={}, headers={"sec-fetch-site": "cross-site"}
        )
        assert response.status_code == 403

    async def test_sign_in_is_covered_too(self, anonymous: AsyncClient) -> None:
        response = await anonymous.post(
            f"{API}/auth/sign-in",
            json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
            headers={"origin": "https://evil.example"},
        )
        assert response.status_code == 403

    async def test_this_origin_and_the_public_url_are_accepted(self, client: AsyncClient) -> None:
        here = await client.post(f"{API}/chats", json={}, headers={"origin": "http://hera.test"})
        assert here.status_code == 201

        save_config(load_config().with_instance(public_url="https://hera.example.com/"))
        behind_a_proxy = await client.post(
            f"{API}/chats", json={}, headers={"origin": "https://hera.example.com"}
        )
        assert behind_a_proxy.status_code == 201

    async def test_a_read_is_not_checked(self, client: AsyncClient) -> None:
        response = await client.get(f"{API}/chats", headers={"origin": "https://evil.example"})
        assert response.status_code == 200

    async def test_over_https_the_cookie_is_secure(self, anonymous: AsyncClient) -> None:
        save_config(load_config().with_instance(public_url="https://hera.example.com"))
        response = await anonymous.post(
            f"{API}/auth/sign-in", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}
        )
        assert "Secure" in response.headers["set-cookie"]


class TestAdmins:
    @pytest.fixture
    async def user_client(self, client: AsyncClient, services: Services) -> AsyncClient:
        client.cookies.clear()
        return sign_in(client, services, make_user(services, "ben@hera.test"))

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("PATCH", "/instance", {"name": "Mine"}),
            ("POST", "/providers", {"name": "x", "base_url": "http://x", "model_id": "m"}),
            ("DELETE", "/servers/x", None),
            ("PUT", "/mind/safety", {"text": "Anything goes."}),
            ("PUT", "/mind/tone?scope=template", {"text": "Shout."}),
            ("GET", "/mind?scope=template", None),
            ("PATCH", "/permissions", {"fallback": "allow"}),
            ("POST", "/skills", {"id": "x", "content": "---\nname: x\n---\n"}),
            ("PATCH", "/preferences", {"timezone": "UTC"}),
            ("GET", "/providers/local/models", None),
        ],
    )
    async def test_an_instance_route_is_a_403_for_a_user(
        self, user_client: AsyncClient, method: str, path: str, body: Any
    ) -> None:
        response = await user_client.request(method, f"{API}{path}", json=body)
        assert response.status_code == 403

    async def test_a_user_can_still_read_and_talk(self, user_client: AsyncClient) -> None:
        assert (await user_client.get(f"{API}/instance")).status_code == 200
        # Their own mind is theirs to edit (ADR 28).
        edited = await user_client.put(f"{API}/mind/tone", json={"text": "Dry."})
        assert edited.status_code == 200
        assert (await user_client.get(f"{API}/providers")).status_code == 200
        assert (await user_client.post(f"{API}/chats", json={})).status_code == 201

    async def test_one_persons_chat_is_a_404_to_another(
        self, client: AsyncClient, services: Services
    ) -> None:
        chat = (await client.post(f"{API}/chats", json={})).json()["id"]
        client.cookies.clear()
        sign_in(client, services, make_user(services, "ben@hera.test"))
        assert (await client.get(f"{API}/chats/{chat}")).status_code == 404
        assert (await client.get(f"{API}/chats")).json() == []

    async def test_an_admin_sets_the_instance(self, client: AsyncClient) -> None:
        body = (
            await client.patch(
                f"{API}/instance",
                json={"name": "Home", "public_url": "https://h.example/", "registration": "open"},
            )
        ).json()
        assert body == {"name": "Home", "public_url": "https://h.example", "registration": "open"}
        assert load_config().instance.registration == "open"
        bad = await client.patch(f"{API}/instance", json={"public_url": "h.example"})
        assert bad.status_code == 422


class TestTheThrottle:
    def test_a_few_mistakes_are_free_and_then_each_one_doubles(self) -> None:
        now = [0.0]
        throttle = Throttle(free=2, ceiling=60, clock=lambda: now[0])
        throttle.failed("a")
        throttle.failed("a")
        assert throttle.wait("a") == 1.0
        throttle.failed("a")
        assert throttle.wait("a") == 2.0
        now[0] += 2
        assert throttle.wait("a", "b") == 0
        for _ in range(20):
            throttle.failed("a")
        assert throttle.wait("a") == 60
        throttle.succeeded("a")
        assert throttle.wait("a") == 0

    def test_it_forgets_old_entries_when_it_grows(self) -> None:
        now = [0.0]
        throttle = Throttle(ceiling=10, clock=lambda: now[0])
        for index in range(10_001):
            throttle.failed(f"k{index}")
        now[0] = 100
        throttle.failed("new")
        assert throttle.wait("k1") == 0
        assert len(throttle._failures) == 1

"""Claiming a fresh instance: the setup wizard's one privileged step (ADR 27).

Loopback needs no code; anything else does — and a request that came through a proxy is
anything else, whatever its peer address says.
"""

from __future__ import annotations

import os
import stat
from datetime import timedelta

import pytest
from core_support import API, unclaim
from httpx import AsyncClient

from hera_accounts import Accounts, Purpose
from hera_core.claim import announce, new_setup_code, normalise_code
from hera_core.wiring import Services
from hera_home import setup_code_path

ADMIN = {"name": "Ada", "email": "Ada@Example.org", "password": "a long password"}
PROXIED = {"x-forwarded-for": "203.0.113.9"}


@pytest.fixture
def fresh(services: Services) -> Services:
    unclaim(services.database)
    return services


class TestTheState:
    async def test_a_fresh_instance_says_so_and_counts_what_becomes_yours(
        self, anonymous: AsyncClient, fresh: Services, client: AsyncClient
    ) -> None:
        # `client` is signed in as the owner, which an unclaimed install still has rows for.
        await client.post(f"{API}/chats", json={})
        client.cookies.clear()

        body = (await anonymous.get(f"{API}/setup")).json()

        assert body == {"required": True, "code_required": False, "chats": 1}
        assert (await anonymous.get(f"{API}/auth/state")).json()["setup_required"] is True

    async def test_through_a_proxy_a_code_is_required(
        self, anonymous: AsyncClient, fresh: Services
    ) -> None:
        body = (await anonymous.get(f"{API}/setup", headers=PROXIED)).json()
        assert body["code_required"] is True

    async def test_a_claimed_instance_needs_nothing(self, anonymous: AsyncClient) -> None:
        assert (await anonymous.get(f"{API}/setup")).json()["required"] is False


class TestClaiming:
    async def test_from_the_machine_itself_it_makes_the_admin_and_signs_them_in(
        self, anonymous: AsyncClient, fresh: Services
    ) -> None:
        response = await anonymous.post(f"{API}/setup", json=ADMIN)

        assert response.status_code == 201
        body = response.json()
        # The owner id: everything the install already has is theirs.
        assert body["id"] == str(fresh.settings.owner_id)
        assert (body["email"], body["role"], body["name"]) == ("ada@example.org", "admin", "Ada")
        assert (await anonymous.get(f"{API}/chats")).status_code == 200

    async def test_it_works_once(self, anonymous: AsyncClient, fresh: Services) -> None:
        await anonymous.post(f"{API}/setup", json=ADMIN)
        again = await anonymous.post(f"{API}/setup", json={**ADMIN, "email": "eve@example.org"})
        assert again.status_code == 409

    async def test_from_elsewhere_it_needs_the_code(
        self, anonymous: AsyncClient, fresh: Services
    ) -> None:
        code = announce(fresh.database)
        assert code is not None

        refused = await anonymous.post(f"{API}/setup", json=ADMIN, headers=PROXIED)
        assert refused.status_code == 403
        assert "setup-code" in refused.json()["detail"]

        typed = code.lower().replace("-", " ")
        made = await anonymous.post(f"{API}/setup", json={**ADMIN, "code": typed}, headers=PROXIED)
        assert made.status_code == 201
        assert not setup_code_path().exists()

    async def test_a_launch_token_stands_in_for_the_code(
        self, anonymous: AsyncClient, fresh: Services
    ) -> None:
        with fresh.database.session() as session:
            token = Accounts(session).issue(Purpose.LAUNCH, lifetime=timedelta(minutes=5))
        made = await anonymous.post(
            f"{API}/setup", json={**ADMIN, "launch_token": token}, headers=PROXIED
        )
        assert made.status_code == 201

    async def test_guessing_the_code_is_slowed_down(
        self, anonymous: AsyncClient, fresh: Services
    ) -> None:
        announce(fresh.database)
        for _ in range(5):
            wrong = await anonymous.post(
                f"{API}/setup", json={**ADMIN, "code": "AAAA-AAAA-AAAA"}, headers=PROXIED
            )
            assert wrong.status_code == 403
        throttled = await anonymous.post(
            f"{API}/setup", json={**ADMIN, "code": "AAAA-AAAA-AAAA"}, headers=PROXIED
        )
        assert throttled.status_code == 429

    async def test_a_bad_password_is_refused_and_nothing_is_spent(
        self, anonymous: AsyncClient, fresh: Services
    ) -> None:
        response = await anonymous.post(f"{API}/setup", json={**ADMIN, "password": "short"})
        assert response.status_code == 422
        assert (await anonymous.get(f"{API}/setup")).json()["required"] is True

    async def test_an_install_from_before_accounts_is_adopted(
        self, anonymous: AsyncClient, fresh: Services
    ) -> None:
        """The migrated owner row has an empty email and no password; claiming fills it in."""
        with fresh.database.session() as session:
            accounts = Accounts(session)
            owner = accounts.get(fresh.settings.owner_id)
            assert owner is not None
            owner.name = "Old name"
            session.add(owner)

        body = (await anonymous.post(f"{API}/setup", json={**ADMIN, "name": ""})).json()

        assert body["name"] == "Old name"
        with fresh.database.session() as session:
            assert len(Accounts(session).users()) == 1


class TestTheCode:
    def test_it_is_written_for_the_owner_alone_and_replaced_each_boot(
        self, fresh: Services
    ) -> None:
        first = announce(fresh.database)
        mode = stat.S_IMODE(os.stat(setup_code_path()).st_mode)
        assert mode == 0o600
        second = announce(fresh.database)
        assert setup_code_path().read_text().strip() == second
        with fresh.database.session() as session:
            accounts = Accounts(session)
            assert first is not None and second is not None
            assert accounts.redeem(Purpose.SETUP, first) is None
            assert accounts.redeem(Purpose.SETUP, second) is not None

    def test_a_claimed_instance_has_none_and_keeps_none(self, services: Services) -> None:
        setup_code_path().parent.mkdir(parents=True, exist_ok=True)
        setup_code_path().write_text("left over")
        assert announce(services.database) is None
        assert not setup_code_path().exists()

    def test_it_is_typeable(self) -> None:
        code = new_setup_code()
        assert len(code) == 14 and code.count("-") == 2
        assert not set(code) & set("01IOL")
        assert normalise_code(code.lower().replace("-", "")) == code
        assert normalise_code("short") == "SHORT"

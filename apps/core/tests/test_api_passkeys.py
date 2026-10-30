"""Passkeys through the real routes, answered by a software authenticator (ADR 27, M4).

The instance's public URL is ``https://hera.test`` here — the address the test client is at, over
https — because WebAuthn works nowhere else: not on an IP address, and not over plain http unless
it is localhost.
"""

from __future__ import annotations

from typing import Any

import pytest
from core_support import API, SoftAuthenticator, sign_in
from httpx import AsyncClient

from hera_accounts import Accounts
from hera_core.auth import SESSION_COOKIE
from hera_core.config import load as load_config
from hera_core.config import save as save_config
from hera_core.wiring import Services


def public_url(url: str) -> None:
    save_config(load_config().with_instance(public_url=url))


@pytest.fixture(autouse=True)
def _over_https() -> None:
    public_url("https://hera.test")


async def register(client: AsyncClient, device: SoftAuthenticator, label: str = "") -> Any:
    started = (await client.post(f"{API}/auth/passkeys/options")).json()
    return await client.post(
        f"{API}/auth/passkeys",
        json={
            "ceremony": started["ceremony"],
            "credential": device.create(started["options"]),
            "label": label,
        },
    )


async def sign_in_with(http: AsyncClient, device: SoftAuthenticator, **answer: Any) -> Any:
    started = (await http.post(f"{API}/auth/passkey/options")).json()
    return await http.post(
        f"{API}/auth/passkey",
        json={
            "ceremony": started["ceremony"],
            "credential": device.get(started["options"], **answer),
        },
    )


class TestWhereTheyWork:
    async def test_only_at_a_name_over_https_or_on_localhost(self, anonymous: AsyncClient) -> None:
        async def offered() -> bool:
            return bool((await anonymous.get(f"{API}/auth/state")).json()["passkeys"])

        assert await offered()
        public_url("https://elsewhere.test")
        assert not await offered(), "a passkey for another host is one the browser refuses"
        public_url("")
        assert not await offered(), "http://hera.test is neither https nor localhost"

        localhost = await anonymous.get("http://localhost/api/v1/auth/state")
        assert localhost.json()["passkeys"] is True
        lan = await anonymous.get("http://192.168.1.20:8756/api/v1/auth/state")
        assert lan.json()["passkeys"] is False

        # A public URL of 0.0.0.0, saved before the screen refused one, names no site at all.
        public_url("http://0.0.0.0:8756")
        assert (await anonymous.get("http://localhost/api/v1/auth/state")).json()["passkeys"]
        public_url("")

        refused = await anonymous.post(f"{API}/auth/passkey/options")
        assert refused.status_code == 409
        assert "https or on localhost" in refused.json()["detail"]


class TestRegistering:
    async def test_a_passkey_is_added_listed_renamed_and_removed(self, client: AsyncClient) -> None:
        added = await register(client, SoftAuthenticator())
        assert added.status_code == 201
        assert added.json()["label"] == "Passkey 1"
        assert added.json()["last_used_at"] is None

        [listed] = (await client.get(f"{API}/auth/passkeys")).json()
        renamed = await client.patch(
            f"{API}/auth/passkeys/{listed['id']}", json={"label": "MacBook"}
        )
        assert renamed.json()["label"] == "MacBook"
        assert (await client.delete(f"{API}/auth/passkeys/{listed['id']}")).status_code == 204
        assert (await client.get(f"{API}/auth/passkeys")).json() == []

    async def test_the_options_leave_out_what_is_already_registered(
        self, client: AsyncClient
    ) -> None:
        device = SoftAuthenticator()
        await register(client, device, label="Phone")
        options = (await client.post(f"{API}/auth/passkeys/options")).json()["options"]

        assert options["rp"] == {"id": "hera.test", "name": "Hera"}
        assert options["authenticatorSelection"]["residentKey"] == "required"
        [excluded] = options["excludeCredentials"]
        assert excluded["transports"] == ["internal"], "an unknown transport is not kept"
        again = await register(client, device)
        assert again.status_code == 400
        assert "already registered" in again.json()["detail"]

    async def test_a_ceremony_works_once_and_only_for_whoever_began_it(
        self, client: AsyncClient, services: Services
    ) -> None:
        started = (await client.post(f"{API}/auth/passkeys/options")).json()
        answer = SoftAuthenticator().create(started["options"])
        body = {"ceremony": started["ceremony"], "credential": answer}

        with services.database.session() as session:
            ben = Accounts(session).create("ben@hera.test").id
        sign_in(client, services, ben)
        assert (await client.post(f"{API}/auth/passkeys", json=body)).status_code == 400
        sign_in(client, services)
        assert (await client.post(f"{API}/auth/passkeys", json=body)).status_code == 400, "spent"

    async def test_an_answer_for_another_site_is_refused(self, client: AsyncClient) -> None:
        added = await register(client, SoftAuthenticator(origin="https://evil.test"))
        assert added.status_code == 400
        assert "could not be verified" in added.json()["detail"]

    async def test_a_ceremony_left_too_long_has_expired(
        self, client: AsyncClient, services: Services
    ) -> None:
        clock = [1000.0]
        services.ceremonies.clock = lambda: clock[0]
        started = (await client.post(f"{API}/auth/passkeys/options")).json()
        clock[0] += 301
        late = await client.post(
            f"{API}/auth/passkeys",
            json={
                "ceremony": started["ceremony"],
                "credential": SoftAuthenticator().create(started["options"]),
            },
        )
        assert late.status_code == 400
        assert "too long" in late.json()["detail"]

    async def test_somebody_elses_passkey_is_not_found(
        self, client: AsyncClient, services: Services
    ) -> None:
        mine = (await register(client, SoftAuthenticator())).json()["id"]
        with services.database.session() as session:
            ben = Accounts(session).create("ben@hera.test").id
        sign_in(client, services, ben)
        assert (
            await client.patch(f"{API}/auth/passkeys/{mine}", json={"label": "Mine now"})
        ).status_code == 404
        assert (await client.delete(f"{API}/auth/passkeys/{mine}")).status_code == 404


class TestSigningIn:
    async def test_no_email_is_typed_and_the_session_is_theirs(
        self, client: AsyncClient, services: Services
    ) -> None:
        device = SoftAuthenticator()
        await register(client, device)
        client.cookies.clear()

        signed = await sign_in_with(client, device)

        assert signed.status_code == 200
        assert signed.json()["id"] == str(services.settings.owner_id)
        assert SESSION_COOKIE in signed.headers["set-cookie"]
        assert "Secure" in signed.headers["set-cookie"], "an https Hera's cookie is https-only"
        with services.database.session() as session:
            [stored] = Accounts(session).passkeys(services.settings.owner_id)
            assert stored.sign_count == 1
            assert stored.last_used_at is not None

    async def test_a_counter_that_went_backwards_is_a_copied_key(self, client: AsyncClient) -> None:
        device = SoftAuthenticator()
        await register(client, device)
        assert (await sign_in_with(client, device, count=5)).status_code == 200
        replayed = await sign_in_with(client, device, count=3)
        assert replayed.status_code == 401

    async def test_a_key_that_did_not_sign_and_a_key_nobody_has_read_the_same(
        self, client: AsyncClient
    ) -> None:
        device = SoftAuthenticator()
        await register(client, device)
        forger = SoftAuthenticator()
        forger.credential_id = device.credential_id  # the right name, the wrong key
        stranger = SoftAuthenticator()

        forged = await sign_in_with(client, forger)
        unknown = await sign_in_with(client, stranger)
        assert forged.status_code == unknown.status_code == 401
        assert forged.json() == unknown.json()

    async def test_a_disabled_account_cannot_sign_in(
        self, client: AsyncClient, services: Services
    ) -> None:
        device = SoftAuthenticator()
        with services.database.session() as session:
            ben = Accounts(session).create("ben@hera.test").id
        sign_in(client, services, ben)
        await register(client, device)
        with services.database.session() as session:
            accounts = Accounts(session)
            user = accounts.get(ben)
            assert user is not None
            accounts.set_disabled(user, True)
        assert (await sign_in_with(client, device)).status_code == 401

    async def test_guessing_is_slowed_down(self, anonymous: AsyncClient) -> None:
        stranger = SoftAuthenticator()
        for _ in range(5):
            assert (await sign_in_with(anonymous, stranger)).status_code == 401
        assert (await sign_in_with(anonymous, stranger)).status_code == 429

    async def test_a_sign_in_ceremony_cannot_be_used_to_register(self, client: AsyncClient) -> None:
        started = (await client.post(f"{API}/auth/passkey/options")).json()
        assert (
            "allowCredentials" not in started["options"]
            or not started["options"]["allowCredentials"]
        )
        made = await client.post(
            f"{API}/auth/passkeys",
            json={
                "ceremony": started["ceremony"],
                "credential": SoftAuthenticator().create(
                    {
                        "challenge": started["options"]["challenge"],
                        "rp": {"id": "hera.test"},
                        "user": {"id": "AAAA"},
                    }
                ),
            },
        )
        assert made.status_code == 400

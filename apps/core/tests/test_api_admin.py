"""Settings → Admin: people, invitations, links, password resets and mail (ADR 27, M3).

Against the real routes, with a postbox where the mail server would be. The assertions that
matter most are the ones about strangers: a reset request that answers the same for every
address, and a link that is built from the instance's own URL whatever ``Host`` the request
claimed.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from core_support import API, OWNER_EMAIL, sign_in
from httpx import AsyncClient

from hera_accounts import Accounts, Role
from hera_chats import ChatRepository
from hera_core.auth import SESSION_COOKIE
from hera_core.config import load as load_config
from hera_core.config import save as save_config
from hera_core.mail import Postbox
from hera_core.wiring import Services
from hera_home import chat_dir, user_dir

PUBLIC = "https://hera.example.com"


def postbox(services: Services) -> Postbox:
    assert isinstance(services.mailer, Postbox)
    return services.mailer


def mail_on(*, public_url: str = PUBLIC) -> None:
    config = load_config().with_mail(host="smtp.hera.test", sender="hera@hera.test")
    save_config(config.with_instance(public_url=public_url))


def set_registration(mode: str) -> None:
    save_config(load_config().with_instance(registration=mode))


def make_user(
    services: Services, email: str, *, role: Role = Role.USER, password: str = ""
) -> UUID:
    with services.database.session() as session:
        return Accounts(session).create(email, role=role, password=password or None).id


def token_of(link: str) -> str:
    return link.split("#", 1)[1]


async def invite(
    client: AsyncClient, email: str = "ben@hera.test", *, headers_host: str = "", **extra: Any
) -> Any:
    headers = {"host": headers_host} if headers_host else {}
    return await client.post(
        f"{API}/invitations", json={"email": email, "name": "Ben", **extra}, headers=headers
    )


class TestMail:
    async def test_the_password_is_written_and_never_read_back(self, client: AsyncClient) -> None:
        saved = await client.patch(
            f"{API}/mail",
            json={"host": " smtp.hera.test ", "port": 465, "security": "tls", "password": "pw"},
        )
        assert saved.status_code == 200
        body = saved.json()
        assert body["host"] == "smtp.hera.test"
        assert "password" not in body
        assert body["password_set"] is True
        assert body["configured"] is False, "no sender yet"
        assert load_config().mail.password == "pw"

        # Left out keeps it; an empty string clears it.
        await client.patch(f"{API}/mail", json={"sender": "hera@hera.test"})
        assert load_config().mail.password == "pw"
        cleared = await client.patch(f"{API}/mail", json={"password": ""})
        assert cleared.json()["password_set"] is False
        assert cleared.json()["configured"] is True
        assert cleared.json()["links_need_public_url"] is True

    async def test_a_pasted_name_and_address_is_split_into_both(
        self, client: AsyncClient, services: Services
    ) -> None:
        saved = await client.patch(
            f"{API}/mail",
            json={"host": "smtp.hera.test", "sender": "Hera <hera@services.hera.test>"},
        )
        assert saved.json()["sender"] == "hera@services.hera.test"
        assert saved.json()["sender_name"] == "Hera"

        await client.post(f"{API}/mail/test")
        assert postbox(services).froms == ["Hera <hera@services.hera.test>"]

    async def test_without_a_from_name_the_instance_is_the_sender(
        self, client: AsyncClient, services: Services
    ) -> None:
        mail_on()
        save_config(load_config().with_instance(name="Home"))
        await client.post(f"{API}/mail/test")
        assert postbox(services).froms == ["Home <hera@hera.test>"]

    async def test_a_sender_has_to_be_an_address(self, client: AsyncClient) -> None:
        refused = await client.patch(f"{API}/mail", json={"sender": "not an address"})
        assert refused.status_code == 422

    async def test_a_test_mail_goes_to_the_admin_asking(
        self, client: AsyncClient, services: Services
    ) -> None:
        unset = await client.post(f"{API}/mail/test")
        assert unset.status_code == 502
        assert "not set up" in unset.json()["detail"]

        mail_on()
        assert (await client.post(f"{API}/mail/test")).status_code == 204
        [letter] = postbox(services).sent
        assert letter.to == OWNER_EMAIL

        postbox(services).failure = "the server said no"
        failed = await client.post(f"{API}/mail/test")
        assert failed.status_code == 502
        assert failed.json()["detail"] == "the server said no"

    async def test_mail_is_an_admins(self, client: AsyncClient, services: Services) -> None:
        sign_in(client, services, make_user(services, "ben@hera.test"))
        assert (await client.get(f"{API}/mail")).status_code == 403
        assert (await client.patch(f"{API}/mail", json={"host": "x"})).status_code == 403
        assert (await client.post(f"{API}/mail/test")).status_code == 403


class TestInvitations:
    async def test_an_invitation_without_mail_is_a_link_to_hand_over(
        self, client: AsyncClient, services: Services
    ) -> None:
        response = await invite(client)

        assert response.status_code == 201
        body = response.json()
        assert body["mailed"] is False
        assert body["mail_error"] == ""
        assert body["link"].startswith("http://hera.test/password#")
        assert body["user"]["invited"] is True
        assert body["user"]["role"] == "user"
        assert postbox(services).sent == []

    async def test_with_mail_it_is_sent_and_says_who_invited_them(
        self, client: AsyncClient, services: Services
    ) -> None:
        mail_on()
        await client.patch(f"{API}/account", json={"name": "Ada"})
        body = (await invite(client, role="admin")).json()

        assert body["mailed"] is True
        assert body["user"]["role"] == "admin"
        assert body["link"].startswith(f"{PUBLIC}/password#")
        [letter] = postbox(services).sent
        assert letter.to == "ben@hera.test"
        assert "Ada has made you an account" in letter.text
        assert body["link"] in letter.text

    async def test_mail_that_fails_still_leaves_a_link(
        self, client: AsyncClient, services: Services
    ) -> None:
        mail_on()
        postbox(services).failure = "connection refused"
        body = (await invite(client)).json()
        assert body["mailed"] is False
        assert body["mail_error"] == "connection refused"
        assert body["link"]

    async def test_an_address_with_an_account_is_refused(self, client: AsyncClient) -> None:
        assert (await invite(client, OWNER_EMAIL.upper())).status_code == 409
        assert (await invite(client, "not an address")).status_code == 422

    async def test_a_member_invites_only_while_registration_is_by_invitation(
        self, client: AsyncClient, services: Services
    ) -> None:
        sign_in(client, services, make_user(services, "cy@hera.test"))
        refused = await invite(client)
        assert refused.status_code == 403

        set_registration("invite")
        assert (await invite(client)).status_code == 201
        as_admin = await invite(client, "dee@hera.test", role="admin")
        assert as_admin.status_code == 403
        assert "admin" in as_admin.json()["detail"]


class TestALink:
    async def test_it_says_who_it_is_for_without_being_spent(
        self, client: AsyncClient, anonymous: AsyncClient
    ) -> None:
        token = token_of((await invite(client)).json()["link"])
        client.cookies.clear()

        for _ in range(2):
            opened = await anonymous.post(f"{API}/auth/link", json={"token": token})
            assert opened.status_code == 200
            assert opened.json() == {
                "purpose": "invite",
                "email": "ben@hera.test",
                "name": "Ben",
                "instance_name": "Hera",
            }

    async def test_choosing_a_password_signs_them_in_and_spends_it(
        self, client: AsyncClient, anonymous: AsyncClient
    ) -> None:
        token = token_of((await invite(client)).json()["link"])
        client.cookies.clear()

        short = await anonymous.post(
            f"{API}/auth/link/password", json={"token": token, "password": "short"}
        )
        assert short.status_code == 422, "and the link still works"
        chosen = await anonymous.post(
            f"{API}/auth/link/password", json={"token": token, "password": "a long password"}
        )
        assert chosen.status_code == 200
        assert chosen.json()["email"] == "ben@hera.test"
        assert SESSION_COOKIE in chosen.headers["set-cookie"]
        assert (await anonymous.get(f"{API}/account")).json()["email"] == "ben@hera.test"

        again = await anonymous.post(f"{API}/auth/link", json={"token": token})
        assert again.status_code == 404
        signed = await anonymous.post(
            f"{API}/auth/sign-in", json={"email": "ben@hera.test", "password": "a long password"}
        )
        assert signed.status_code == 200

    async def test_a_made_up_link_or_a_disabled_account_is_dead(
        self, client: AsyncClient, anonymous: AsyncClient
    ) -> None:
        body = (await invite(client)).json()
        await client.patch(f"{API}/users/{body['user']['id']}", json={"disabled": True})
        client.cookies.clear()

        for token in ("made-up", token_of(body["link"])):
            assert (
                await anonymous.post(f"{API}/auth/link", json={"token": token})
            ).status_code == 404
            used = await anonymous.post(
                f"{API}/auth/link/password", json={"token": token, "password": "a long password"}
            )
            assert used.status_code == 404


class TestForgotPassword:
    async def test_without_mail_and_a_public_url_it_is_not_offered(
        self, anonymous: AsyncClient
    ) -> None:
        assert (await anonymous.get(f"{API}/auth/state")).json()["reset_by_mail"] is False
        refused = await anonymous.post(f"{API}/auth/reset", json={"email": OWNER_EMAIL})
        assert refused.status_code == 409
        assert "ask an admin" in refused.json()["detail"]

        mail_on(public_url="")
        assert (await anonymous.get(f"{API}/auth/state")).json()["reset_by_mail"] is False

    async def test_every_address_gets_the_same_answer_and_only_a_real_one_mail(
        self, anonymous: AsyncClient, services: Services
    ) -> None:
        mail_on()
        assert (await anonymous.get(f"{API}/auth/state")).json()["reset_by_mail"] is True

        known = await anonymous.post(f"{API}/auth/reset", json={"email": OWNER_EMAIL.upper()})
        unknown = await anonymous.post(f"{API}/auth/reset", json={"email": "nobody@hera.test"})
        assert known.status_code == unknown.status_code == 202
        assert known.content == unknown.content
        [letter] = postbox(services).sent
        assert letter.to == OWNER_EMAIL

    async def test_the_link_points_at_the_public_url_whatever_host_was_claimed(
        self, anonymous: AsyncClient, services: Services
    ) -> None:
        mail_on()
        await anonymous.post(
            f"{API}/auth/reset", json={"email": OWNER_EMAIL}, headers={"host": "evil.example"}
        )
        [letter] = postbox(services).sent
        assert f"{PUBLIC}/password#" in letter.text
        assert "evil.example" not in letter.text

    async def test_a_reset_signs_out_everywhere_and_only_the_newest_link_works(
        self, client: AsyncClient, anonymous: AsyncClient, services: Services
    ) -> None:
        mail_on()
        for _ in range(2):
            await anonymous.post(f"{API}/auth/reset", json={"email": OWNER_EMAIL})
        first, second = _tokens(postbox(services))
        client.cookies.clear()

        assert (await anonymous.post(f"{API}/auth/link", json={"token": first})).status_code == 404
        opened = await anonymous.post(f"{API}/auth/link", json={"token": second})
        assert opened.json()["purpose"] == "reset"

        with services.database.session() as session:
            Accounts(session).open_session(services.settings.owner_id)  # another browser
        done = await anonymous.post(
            f"{API}/auth/link/password", json={"token": second, "password": "a brand new one"}
        )
        assert done.status_code == 200
        with services.database.session() as session:
            assert len(Accounts(session).sessions(services.settings.owner_id)) == 1

    async def test_asking_again_and_again_is_slowed_down(self, anonymous: AsyncClient) -> None:
        mail_on()
        for _ in range(5):
            response = await anonymous.post(f"{API}/auth/reset", json={"email": OWNER_EMAIL})
            assert response.status_code == 202
        slowed = await anonymous.post(f"{API}/auth/reset", json={"email": OWNER_EMAIL})
        assert slowed.status_code == 429

    async def test_a_disabled_account_gets_no_mail(
        self, anonymous: AsyncClient, services: Services
    ) -> None:
        mail_on()
        ben = make_user(services, "ben@hera.test", password="a long password")
        with services.database.session() as session:
            accounts = Accounts(session)
            user = accounts.get(ben)
            assert user is not None
            accounts.set_disabled(user, True)
        await anonymous.post(f"{API}/auth/reset", json={"email": "ben@hera.test"})
        assert postbox(services).sent == []


def _tokens(box: Postbox) -> list[str]:
    return [token_of(next(w for w in letter.text.split() if "#" in w)) for letter in box.sent]


class TestUsers:
    async def test_the_list_says_who_is_invited_and_who_was_seen(self, client: AsyncClient) -> None:
        await invite(client)
        await client.get(f"{API}/chats")
        users = {u["email"]: u for u in (await client.get(f"{API}/users")).json()}

        assert users[OWNER_EMAIL]["invited"] is False
        assert users[OWNER_EMAIL]["last_seen_at"] is not None
        assert users["ben@hera.test"]["invited"] is True
        assert users["ben@hera.test"]["last_seen_at"] is None

    async def test_roles_change_but_never_leave_nobody_in_charge(
        self, client: AsyncClient, services: Services
    ) -> None:
        owner = services.settings.owner_id
        ben = make_user(services, "ben@hera.test")

        promoted = await client.patch(f"{API}/users/{ben}", json={"role": "admin"})
        assert promoted.json()["role"] == "admin"
        await client.patch(f"{API}/users/{ben}", json={"role": "user"})
        last = await client.patch(f"{API}/users/{owner}", json={"role": "user"})
        assert last.status_code == 409
        assert (await client.patch(f"{API}/users/{UUID(int=1)}", json={})).status_code == 404

    async def test_disabling_signs_them_out_and_is_not_for_yourself(
        self, client: AsyncClient, services: Services
    ) -> None:
        ben = make_user(services, "ben@hera.test")
        with services.database.session() as session:
            Accounts(session).open_session(ben)

        disabled = await client.patch(f"{API}/users/{ben}", json={"disabled": True})
        assert disabled.json()["disabled"] is True
        with services.database.session() as session:
            assert Accounts(session).sessions(ben) == []
        own = await client.patch(
            f"{API}/users/{services.settings.owner_id}", json={"disabled": True}
        )
        assert own.status_code == 409
        refused = await client.post(f"{API}/users/{ben}/link")
        assert refused.status_code == 409

    async def test_a_link_for_somebody_with_a_password_is_a_reset(
        self, client: AsyncClient, services: Services
    ) -> None:
        ben = make_user(services, "ben@hera.test", password="a long password")
        sent = (await client.post(f"{API}/users/{ben}/link")).json()
        opened = await client.post(f"{API}/auth/link", json={"token": token_of(sent["link"])})
        assert opened.json()["purpose"] == "reset"

    async def test_copying_a_link_makes_a_new_one_without_mailing_it(
        self, client: AsyncClient, services: Services
    ) -> None:
        mail_on()
        first = (await invite(client)).json()
        assert first["mailed"] is True
        ben = first["user"]["id"]

        copied = (await client.post(f"{API}/users/{ben}/link?mail=false")).json()
        assert copied["mailed"] is False
        assert copied["link"] != first["link"]
        assert len(postbox(services).sent) == 1, "nothing new in the mailbox"

        dead = await client.post(f"{API}/auth/link", json={"token": token_of(first["link"])})
        assert dead.status_code == 404, "the mailed link is replaced, not kept alongside"
        live = await client.post(f"{API}/auth/link", json={"token": token_of(copied["link"])})
        assert live.json()["purpose"] == "invite"

    async def test_signing_somebody_out_everywhere(
        self, client: AsyncClient, services: Services
    ) -> None:
        ben = make_user(services, "ben@hera.test")
        with services.database.session() as session:
            Accounts(session).open_session(ben)
        assert (await client.delete(f"{API}/users/{ben}/sessions")).status_code == 204
        with services.database.session() as session:
            assert Accounts(session).sessions(ben) == []

    async def test_deleting_somebody_takes_everything_of_theirs(
        self, client: AsyncClient, services: Services
    ) -> None:
        ben = make_user(services, "ben@hera.test", password="a long password")
        sign_in(client, services, ben)
        chat = (await client.post(f"{API}/chats", json={})).json()["id"]
        await client.put(f"{API}/mind/tone", json={"text": "Ben's own."})
        chat_dir(chat).mkdir(parents=True, exist_ok=True)
        assert user_dir(str(ben)).is_dir()
        client.cookies.clear()
        sign_in(client, services)

        assert (await client.delete(f"{API}/users/{ben}")).status_code == 204

        with services.database.session() as session:
            assert Accounts(session).get(ben) is None
            assert ChatRepository(session).get(UUID(chat)) is None
        assert not user_dir(str(ben)).exists()
        assert not chat_dir(chat).exists()
        listed = [u["email"] for u in (await client.get(f"{API}/users")).json()]
        assert listed == [OWNER_EMAIL]

    async def test_nobody_deletes_themselves(self, client: AsyncClient, services: Services) -> None:
        own = await client.delete(f"{API}/users/{services.settings.owner_id}")
        assert own.status_code == 409

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/users"),
            ("PATCH", "/users/{id}"),
            ("POST", "/users/{id}/link"),
            ("DELETE", "/users/{id}/sessions"),
            ("DELETE", "/users/{id}"),
        ],
    )
    async def test_users_are_an_admins(
        self, client: AsyncClient, services: Services, method: str, path: str
    ) -> None:
        ben = make_user(services, "ben@hera.test")
        sign_in(client, services, ben)
        response = await client.request(
            method, f"{API}{path.format(id=services.settings.owner_id)}", json={}
        )
        assert response.status_code == 403


class TestAddresses:
    """A link never sends somebody to their own machine (hera_core.addresses)."""

    @pytest.fixture
    def everywhere(self, services: Services, monkeypatch: pytest.MonkeyPatch) -> None:
        from hera_core import addresses

        monkeypatch.setattr(addresses, "lan_address", lambda: "192.168.1.20")
        services.settings = services.settings.model_copy(update={"host": "0.0.0.0"})

    async def test_an_invitation_from_a_browser_at_0000_points_at_the_lan(
        self, client: AsyncClient, everywhere: None
    ) -> None:
        body = (await invite(client, headers_host="0.0.0.0:8756")).json()
        assert body["link"].startswith("http://192.168.1.20:8756/password#")

    async def test_the_wizard_is_offered_an_address_others_can_open(
        self, client: AsyncClient, everywhere: None
    ) -> None:
        shown = await client.get(f"{API}/instance", headers={"host": "localhost:8756"})
        assert shown.json()["suggested_url"] == "http://192.168.1.20:8756"

    async def test_0000_is_not_a_public_url(self, client: AsyncClient) -> None:
        refused = await client.patch(f"{API}/instance", json={"public_url": "http://0.0.0.0:8756"})
        assert refused.status_code == 422
        assert "every address of this machine" in refused.text

    async def test_one_saved_before_is_corrected_in_the_mail(
        self, anonymous: AsyncClient, services: Services, everywhere: None
    ) -> None:
        mail_on(public_url="http://0.0.0.0:8756")
        await anonymous.post(f"{API}/auth/reset", json={"email": OWNER_EMAIL})
        [letter] = postbox(services).sent
        assert "http://192.168.1.20:8756/password#" in letter.text

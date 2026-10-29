"""The signed-in person's account: the record they sign in as.

What is worth asserting is the edges: an email is checked, kept unique and cannot be cleared, a
name is not checked, and an avatar is held to what an image attachment is held to — and is one
person's, not the install's.
"""

from __future__ import annotations

import base64

from core_support import API, OWNER_EMAIL, sign_in
from httpx import AsyncClient

from hera_accounts import Accounts
from hera_core.wiring import Services
from hera_home import avatar_path

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def data_url(raw: bytes, media_type: str = "image/png") -> str:
    return f"data:{media_type};base64,{base64.b64encode(raw).decode()}"


class TestTheRecord:
    async def test_it_is_who_is_signed_in(self, client: AsyncClient, services: Services) -> None:
        body = (await client.get(f"{API}/account")).json()

        assert body == {
            "id": str(services.settings.owner_id),
            "name": "",
            "email": OWNER_EMAIL,
            "role": "admin",
            "avatar_version": 0,
        }

    async def test_it_changes_one_field_at_a_time(self, client: AsyncClient) -> None:
        await client.patch(f"{API}/account", json={"name": "  Ada  "})
        body = (await client.patch(f"{API}/account", json={"email": "ada@example.org"})).json()

        assert body["name"] == "Ada"
        assert body["email"] == "ada@example.org"
        assert (await client.get(f"{API}/account")).json() == body

    async def test_an_email_cannot_be_cleared_because_it_is_how_you_sign_in(
        self, client: AsyncClient
    ) -> None:
        assert (await client.patch(f"{API}/account", json={"email": ""})).status_code == 422
        assert (await client.patch(f"{API}/account", json={"name": ""})).json()["name"] == ""

    async def test_an_email_somebody_else_has_is_refused(
        self, client: AsyncClient, services: Services
    ) -> None:
        with services.database.session() as session:
            Accounts(session).create("ben@example.org")

        response = await client.patch(f"{API}/account", json={"email": "Ben@example.org"})

        assert response.status_code == 409

    async def test_an_email_that_is_not_one_is_refused(self, client: AsyncClient) -> None:
        response = await client.patch(f"{API}/account", json={"email": "not an email"})

        assert response.status_code == 422


class TestTheAvatar:
    async def test_each_person_has_their_own(self, client: AsyncClient, services: Services) -> None:
        await client.put(f"{API}/account/avatar", json={"data_url": data_url(PNG)})
        assert avatar_path(str(services.settings.owner_id)).read_bytes() == PNG

        with services.database.session() as session:
            ben = Accounts(session).create("ben@example.org").id
        client.cookies.clear()
        sign_in(client, services, ben)

        assert (await client.get(f"{API}/account/avatar")).status_code == 404

    async def test_it_is_stored_and_served_back_with_its_type(self, client: AsyncClient) -> None:
        put = await client.put(f"{API}/account/avatar", json={"data_url": data_url(PNG)})

        assert put.status_code == 200
        assert put.json()["avatar_version"] > 0
        served = await client.get(f"{API}/account/avatar")
        assert served.content == PNG
        assert served.headers["content-type"] == "image/png"
        assert served.headers["x-content-type-options"] == "nosniff"

    async def test_there_is_nothing_to_serve_before_one_is_set(self, client: AsyncClient) -> None:
        assert (await client.get(f"{API}/account/avatar")).status_code == 404

    async def test_removing_it_removes_the_file_too(self, client: AsyncClient) -> None:
        await client.put(f"{API}/account/avatar", json={"data_url": data_url(PNG)})

        body = (await client.delete(f"{API}/account/avatar")).json()

        assert body["avatar_version"] == 0
        assert (await client.get(f"{API}/account/avatar")).status_code == 404

    async def test_a_type_that_is_not_a_picture_is_refused(self, client: AsyncClient) -> None:
        response = await client.put(
            f"{API}/account/avatar", json={"data_url": data_url(b"<svg/>", "image/svg+xml")}
        )

        assert response.status_code == 422

    async def test_bytes_that_disagree_with_the_header_are_refused(
        self, client: AsyncClient
    ) -> None:
        response = await client.put(
            f"{API}/account/avatar", json={"data_url": data_url(b"<html>", "image/png")}
        )

        assert response.status_code == 422

    async def test_a_picture_over_the_attachment_limit_is_refused(
        self, client: AsyncClient
    ) -> None:
        big = PNG + b"\x00" * (12 * 1024 * 1024)

        response = await client.put(f"{API}/account/avatar", json={"data_url": data_url(big)})

        assert response.status_code == 422

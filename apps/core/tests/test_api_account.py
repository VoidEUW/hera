"""The owner's account: a record with no login behind it.

What is worth asserting is the edges: a first read does not need a write before it, an email is
checked and a name is not, and an avatar is held to what an image attachment is held to.
"""

from __future__ import annotations

import base64

from core_support import API
from httpx import AsyncClient

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def data_url(raw: bytes, media_type: str = "image/png") -> str:
    return f"data:{media_type};base64,{base64.b64encode(raw).decode()}"


class TestTheRecord:
    async def test_a_new_install_has_an_empty_account(self, client: AsyncClient) -> None:
        body = (await client.get(f"{API}/account")).json()

        assert body == {"name": "", "email": "", "avatar_version": 0}

    async def test_it_changes_one_field_at_a_time(self, client: AsyncClient) -> None:
        await client.patch(f"{API}/account", json={"name": "  Ada  "})
        body = (await client.patch(f"{API}/account", json={"email": "ada@example.org"})).json()

        assert body["name"] == "Ada"
        assert body["email"] == "ada@example.org"
        assert (await client.get(f"{API}/account")).json() == body

    async def test_an_empty_string_clears_a_field(self, client: AsyncClient) -> None:
        await client.patch(f"{API}/account", json={"email": "ada@example.org"})

        body = (await client.patch(f"{API}/account", json={"email": ""})).json()

        assert body["email"] == ""

    async def test_an_email_that_is_not_one_is_refused(self, client: AsyncClient) -> None:
        response = await client.patch(f"{API}/account", json={"email": "not an email"})

        assert response.status_code == 422


class TestTheAvatar:
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

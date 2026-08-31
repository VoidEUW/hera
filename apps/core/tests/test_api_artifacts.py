"""What she published in one conversation, over the API the panel beside it reads.

Three routes over a directory (ADR 13). Most of what is worth asserting here is not the happy
path — it is the two things this router exists to hold: an artifact is never served as HTML from
Hera's own origin, and a name that is not a filename is somebody's mistake rather than a missing
file.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from core_support import API
from httpx import AsyncClient

from hera_core.chat_files import FileArtifacts, FileScratchpad
from hera_home import artifacts_dir


async def a_chat(client: AsyncClient) -> str:
    return str((await client.post(f"{API}/chats", json={})).json()["id"])


@pytest.fixture
def published() -> FileArtifacts:
    return FileArtifacts()


class TestListing:
    async def test_it_lists_what_was_published_with_sizes(
        self, client: AsyncClient, published: FileArtifacts
    ) -> None:
        chat_id = await a_chat(client)
        await published.create(chat_id, "page.html", "<h1>Hi</h1>")

        listed = (await client.get(f"{API}/chats/{chat_id}/artifacts")).json()

        assert [(item["name"], item["bytes"]) for item in listed] == [("page.html", 11)]
        assert listed[0]["modified_at"]

    async def test_a_conversation_with_none_is_an_empty_list_rather_than_a_404(
        self, client: AsyncClient
    ) -> None:
        """Publishing nothing is the ordinary state of a conversation, and a 404 would make it
        look the same as no such chat to the file bar."""
        chat_id = await a_chat(client)

        response = await client.get(f"{API}/chats/{chat_id}/artifacts")

        assert response.status_code == 200
        assert response.json() == []

    async def test_the_scratchpad_is_not_listed(
        self, client: AsyncClient, published: FileArtifacts
    ) -> None:
        """ADR 12's promise, enforced at the one place it could be broken: a person browsing for
        the deliverable must not be shown her working notes."""
        chat_id = await a_chat(client)
        await FileScratchpad().write(chat_id, "plan.md", "hers")

        assert (await client.get(f"{API}/chats/{chat_id}/artifacts")).json() == []

    async def test_another_owners_chat_is_a_404(self, client: AsyncClient) -> None:
        assert (await client.get(f"{API}/chats/{uuid4()}/artifacts")).status_code == 404


class TestReading:
    async def test_it_gives_back_the_current_content(
        self, client: AsyncClient, published: FileArtifacts
    ) -> None:
        """*Current* rather than *as published*: an artifact has one state everywhere it
        appears, so an edit in a later turn changes what an earlier card draws."""
        chat_id = await a_chat(client)
        await published.create(chat_id, "page.html", "<h1>Hi</h1>")
        await published.edit(chat_id, "page.html", "Hi", "Hello")

        body = (await client.get(f"{API}/chats/{chat_id}/artifacts/page.html")).json()

        assert body == {"name": "page.html", "bytes": 14, "text": "<h1>Hello</h1>"}

    async def test_it_is_json_rather_than_the_page_itself(
        self, client: AsyncClient, published: FileArtifacts
    ) -> None:
        """The security decision this module holds. Serving a document a *model* wrote as
        `text/html` from Hera's own origin would put it inside the origin holding Hera's
        storage, cookies and DOM — which is exactly what the sandboxed frame in the browser
        exists to prevent, and it would be undone here rather than there."""
        chat_id = await a_chat(client)
        await published.create(chat_id, "page.html", "<script>alert(1)</script>")

        response = await client.get(f"{API}/chats/{chat_id}/artifacts/page.html")

        assert response.headers["content-type"].startswith("application/json")

    async def test_something_never_published_is_a_404(self, client: AsyncClient) -> None:
        chat_id = await a_chat(client)

        assert (await client.get(f"{API}/chats/{chat_id}/artifacts/gone.md")).status_code == 404

    @pytest.mark.parametrize("name", ["sub%5Cplan.md", "%20"])
    async def test_a_name_that_is_not_a_filename_is_a_400_rather_than_a_404(
        self, client: AsyncClient, name: str
    ) -> None:
        """Different mistakes, different answers: a 404 for `..\\config.toml` reads as *try
        another path*, which is the wrong thing to teach a caller that asked wrongly."""
        chat_id = await a_chat(client)

        response = await client.get(f"{API}/chats/{chat_id}/artifacts/{name}")

        assert response.status_code == 400

    async def test_a_name_with_a_slash_in_it_never_reaches_the_route(
        self, client: AsyncClient
    ) -> None:
        """Worth an assertion of its own because the answer is a 404 rather than the 400 above,
        and the reason is somebody else's: a path parameter matches one segment, so `../` is
        refused by routing before the name guard is asked. Both refusals are correct and the
        guard is still the one this rests on — a directory traversal that arrives some other
        way, through a symlink, only ever meets that one."""
        chat_id = await a_chat(client)

        response = await client.get(f"{API}/chats/{chat_id}/artifacts/sub/plan.md")

        assert response.status_code == 404

    async def test_it_cannot_reach_another_conversations_artifacts(
        self, client: AsyncClient, published: FileArtifacts
    ) -> None:
        mine = await a_chat(client)
        theirs = await a_chat(client)
        await published.create(theirs, "page.html", "theirs")

        assert (await client.get(f"{API}/chats/{mine}/artifacts/page.html")).status_code == 404


class TestDownloading:
    async def test_it_comes_back_as_an_attachment_and_not_as_a_page(
        self, client: AsyncClient, published: FileArtifacts
    ) -> None:
        """`Content-Disposition` names the file, the media type is neutral, and `nosniff` stops
        a browser deciding for itself that these bytes are a document worth rendering."""
        chat_id = await a_chat(client)
        await published.create(chat_id, "page.html", "<h1>Hi</h1>")

        response = await client.get(f"{API}/chats/{chat_id}/artifacts/page.html/download")

        assert response.status_code == 200
        assert response.content == b"<h1>Hi</h1>"
        assert response.headers["content-type"] == "application/octet-stream"
        assert response.headers["content-disposition"] == 'attachment; filename="page.html"'
        assert response.headers["x-content-type-options"] == "nosniff"

    async def test_downloading_something_never_published_is_a_404(
        self, client: AsyncClient
    ) -> None:
        chat_id = await a_chat(client)

        response = await client.get(f"{API}/chats/{chat_id}/artifacts/gone.md/download")

        assert response.status_code == 404

    async def test_a_file_that_is_not_text_still_downloads(
        self, client: AsyncClient, published: FileArtifacts
    ) -> None:
        """Everything she writes through the tool is text, so this one arrived some other way —
        and somebody saving a file wants the file rather than an opinion about it."""
        chat_id = await a_chat(client)
        await published.create(chat_id, "logo.png", "placeholder")
        target = (await client.get(f"{API}/chats/{chat_id}/artifacts")).json()[0]["name"]
        (artifacts_dir(chat_id) / target).write_bytes(b"\x89PNG\r\n\x1a\n\xff")

        response = await client.get(f"{API}/chats/{chat_id}/artifacts/logo.png/download")

        assert response.content == b"\x89PNG\r\n\x1a\n\xff"

    async def test_reading_one_that_is_not_text_is_refused_in_words(
        self, client: AsyncClient, published: FileArtifacts
    ) -> None:
        """The panel asked for text and this is not any. Saying so beats handing back
        replacement characters, which is a lie about the contents in the shape of an answer."""
        chat_id = await a_chat(client)
        await published.create(chat_id, "logo.png", "placeholder")
        (artifacts_dir(chat_id) / "logo.png").write_bytes(b"\xff\xfe\x00")

        response = await client.get(f"{API}/chats/{chat_id}/artifacts/logo.png")

        assert response.status_code == 400
        assert "not text" in response.json()["detail"]

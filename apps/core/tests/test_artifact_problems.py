"""A browser saying it could not draw something, and what she is told about it.

Only the browser can tell whether a diagram parses, so the report is the whole mechanism — and
what matters about it is that it goes away when the file changes, because a complaint about a
diagram she already fixed sends her to fix it twice.
"""

from __future__ import annotations

import pytest
from core_support import API
from httpx import AsyncClient

from hera_core.chat_files import FileArtifacts
from hera_core.problems import MAX_MESSAGE, problems


async def a_chat(client: AsyncClient) -> str:
    return str((await client.post(f"{API}/chats", json={})).json()["id"])


async def report(client: AsyncClient, chat_id: str, name: str, message: str) -> int:
    response = await client.put(
        f"{API}/chats/{chat_id}/artifacts/{name}/problem", json={"message": message}
    )
    return response.status_code


class TestReporting:
    async def test_a_report_reaches_the_next_turn(self, client: AsyncClient) -> None:
        chat_id = await a_chat(client)
        await FileArtifacts().create(chat_id, "gdp.mmd", "xychart\n")

        assert await report(client, chat_id, "gdp.mmd", "Lexical error on line 2") == 204

        told = problems.recall(chat_id)
        assert "`gdp.mmd`" in told
        assert "Lexical error on line 2" in told

    async def test_nothing_reported_is_nothing_said(self, client: AsyncClient) -> None:
        assert problems.recall(await a_chat(client)) == ""

    async def test_an_edit_answers_the_report(self, client: AsyncClient) -> None:
        chat_id = await a_chat(client)
        await FileArtifacts().create(chat_id, "gdp.mmd", "xychart\n")
        await report(client, chat_id, "gdp.mmd", "broken")

        await FileArtifacts().create(chat_id, "gdp.mmd", "xychart-beta\n")

        assert problems.recall(chat_id) == ""

    async def test_reports_stay_with_their_conversation(self, client: AsyncClient) -> None:
        mine, other = await a_chat(client), await a_chat(client)
        await FileArtifacts().create(mine, "a.mmd", "x")
        await report(client, mine, "a.mmd", "broken")

        assert problems.recall(other) == ""

    async def test_a_long_message_is_cut_and_flattened(self, client: AsyncClient) -> None:
        chat_id = await a_chat(client)
        await FileArtifacts().create(chat_id, "a.mmd", "x")
        await report(client, chat_id, "a.mmd", "line one\n" + "x" * 1000)

        told = problems.recall(chat_id)

        assert "\n\n" not in told
        assert len(told.splitlines()[-1]) < MAX_MESSAGE + 40

    async def test_a_file_that_is_not_there_is_a_404(self, client: AsyncClient) -> None:
        assert await report(client, await a_chat(client), "ghost.mmd", "broken") == 404

    @pytest.mark.parametrize("name", ["..%2Fconfig.toml", "%2Fetc%2Fpasswd"])
    async def test_a_name_that_is_not_a_filename_reports_nothing(
        self, client: AsyncClient, name: str
    ) -> None:
        assert await report(client, await a_chat(client), name, "broken") in {404, 405}

"""What she knows about you, over the API the settings screen reads (ADR 16).

Five routes over a directory. What is worth asserting here is mostly not the happy path: it is
the two lines this router holds. Deleting is a person's and only a person's, and the export is
lossless — the one that turns *your memories are yours* from a sentence into something you can
check.
"""

from __future__ import annotations

from core_support import API
from httpx import AsyncClient

from hera_core.wiring import Services
from hera_memories import MemoriesSettings


class TestListing:
    async def test_it_lists_everything_the_file_carries(
        self, client: AsyncClient, services: Services
    ) -> None:
        """Including the two fields a turn never sees. The description and the ``why`` are not
        injected, so this screen is the only reason either is worth storing — a list that
        dropped them would make them dead weight on disk."""
        services.memories.write(
            "runs-models-locally",
            "They run LM Studio on an M-series Mac.",
            description="Runs local models on Apple silicon",
            why="Corrected me after I suggested CUDA flags",
        )

        listed = (await client.get(f"{API}/memories")).json()

        assert len(listed) == 1
        assert listed[0]["key"] == "runs-models-locally"
        assert listed[0]["description"] == "Runs local models on Apple silicon"
        assert listed[0]["why"] == "Corrected me after I suggested CUDA flags"
        assert listed[0]["enabled"] is True
        assert listed[0]["tokens"] > 0

    async def test_a_switched_off_memory_is_still_in_the_list(
        self, client: AsyncClient, services: Services
    ) -> None:
        """Not behind a *show disabled* toggle. The switch is about what a turn costs, and a
        list that hid what you switched off would leave you unable to switch it back on."""
        services.memories.write("kept", "A fact.")
        services.memories.set_enabled("kept", False)

        listed = (await client.get(f"{API}/memories")).json()

        assert [(item["key"], item["enabled"]) for item in listed] == [("kept", False)]

    async def test_nothing_remembered_is_an_empty_list(self, client: AsyncClient) -> None:
        response = await client.get(f"{API}/memories")

        assert response.status_code == 200
        assert response.json() == []

    async def test_a_badly_edited_file_is_listed_with_the_reason(
        self, client: AsyncClient, services: Services
    ) -> None:
        """Somebody will open one of these in an editor. A Hera that refuses to answer over one
        stray colon is worse than one memory shown with a complaint beside it."""
        services.memories.directory.mkdir(parents=True, exist_ok=True)
        (services.memories.directory / "odd.md").write_text(
            "---\ndescription: a: b: c\n---\n\nStill readable.\n", encoding="utf-8"
        )

        listed = (await client.get(f"{API}/memories")).json()

        assert listed[0]["text"] == "Still readable."
        assert any("not valid YAML" in problem for problem in listed[0]["problems"])


class TestTheBar:
    async def test_it_reports_what_is_used_against_the_ceiling(
        self, client: AsyncClient, services: Services
    ) -> None:
        services.memories.write("first", "x" * 400)

        budget = (await client.get(f"{API}/memories/budget")).json()

        assert budget["used"] == 100
        assert budget["limit"] == 4000
        assert budget["count"] == 1
        assert budget["disabled"] == 0

    async def test_the_limit_travels_with_the_number_rather_than_being_guessed(
        self, client: AsyncClient, services: Services
    ) -> None:
        """A bar drawn against a constant the browser also knows would be wrong on exactly the
        installs that changed the setting."""
        services.memories.settings = MemoriesSettings(budget_tokens=500)

        assert (await client.get(f"{API}/memories/budget")).json()["limit"] == 500

    async def test_switching_one_off_gives_the_space_back(
        self, client: AsyncClient, services: Services
    ) -> None:
        services.memories.write("first", "x" * 400)

        await client.patch(f"{API}/memories/first", json={"enabled": False})

        budget = (await client.get(f"{API}/memories/budget")).json()
        assert budget["used"] == 0
        assert budget["disabled"] == 1


class TestSwitching:
    async def test_it_comes_back_with_the_memory_as_it_now_is(
        self, client: AsyncClient, services: Services
    ) -> None:
        services.memories.write("first", "A fact.")

        response = await client.patch(f"{API}/memories/first", json={"enabled": False})

        assert response.status_code == 200
        assert response.json()["enabled"] is False
        assert services.memories.recall() == ""

    async def test_switching_one_back_on_when_there_is_no_room_is_a_409(
        self, client: AsyncClient, services: Services
    ) -> None:
        """Nothing about the request was wrong — the store is full, which is a different answer
        from *you asked badly*, and the message says what is taking the space."""
        services.memories.settings = MemoriesSettings(budget_tokens=40)
        services.memories.write("first", "x" * 100)
        services.memories.set_enabled("first", False)
        services.memories.write("second", "y" * 100)

        response = await client.patch(f"{API}/memories/first", json={"enabled": True})

        assert response.status_code == 409
        assert "no room" in response.json()["detail"]

    async def test_a_memory_that_is_not_there_is_a_404(self, client: AsyncClient) -> None:
        response = await client.patch(f"{API}/memories/nothing-here", json={"enabled": False})

        assert response.status_code == 404

    async def test_a_key_that_could_never_name_one_is_a_400(self, client: AsyncClient) -> None:
        """A different mistake from *there is no such memory*, and *try another one* is only
        useful advice for the second."""
        response = await client.patch(f"{API}/memories/Not%20A%20Key", json={"enabled": False})

        assert response.status_code == 400


class TestDeleting:
    async def test_a_person_can_remove_one(self, client: AsyncClient, services: Services) -> None:
        """The other half of *nothing a person told her is discarded without a person present*:
        her own ``forget`` keeps the file, and this route is the only thing that unlinks it."""
        services.memories.write("first", "A fact.")

        response = await client.delete(f"{API}/memories/first")

        assert response.status_code == 204
        assert services.memories.all() == []

    async def test_deleting_one_that_is_gone_is_a_404(self, client: AsyncClient) -> None:
        assert (await client.delete(f"{API}/memories/nothing-here")).status_code == 404

    async def test_a_traversing_key_never_reaches_the_filesystem(self, client: AsyncClient) -> None:
        response = await client.delete(f"{API}/memories/..%5Cconfig.toml")

        assert response.status_code == 400


class TestExport:
    async def test_it_is_the_files_verbatim_so_it_can_be_split_back(
        self, client: AsyncClient, services: Services
    ) -> None:
        services.memories.write("first", "A fact.", description="The first", why="They said so")

        response = await client.get(f"{API}/memories/export/MEMORY.md")

        body = response.text
        assert "## first" in body
        assert "description: The first" in body
        assert "why: They said so" in body
        assert "A fact." in body

    async def test_it_arrives_as_a_file_rather_than_as_a_page(
        self, client: AsyncClient, services: Services
    ) -> None:
        """Partly assembled from text a model wrote, so Hera's own origin is not where it gets
        rendered — the same line `api.artifacts` holds."""
        services.memories.write("first", "A fact.")

        response = await client.get(f"{API}/memories/export/MEMORY.md")

        assert 'attachment; filename="MEMORY.md"' in response.headers["content-disposition"]
        assert response.headers["x-content-type-options"] == "nosniff"

    async def test_a_switched_off_memory_is_still_exported(
        self, client: AsyncClient, services: Services
    ) -> None:
        """A backup that quietly omitted everything you had switched off would be the worst
        kind of surprise to discover from."""
        services.memories.write("kept", "A fact.")
        services.memories.set_enabled("kept", False)

        assert "## kept" in (await client.get(f"{API}/memories/export/MEMORY.md")).text


class TestEditing:
    """The door a *person* has to what she wrote down. Her own tools reach a different one —
    `remember` replaces a whole memory by key, `forget` only ever switches."""

    async def test_the_wording_can_be_corrected(
        self, client: AsyncClient, services: Services
    ) -> None:
        services.memories.write("a-fact", "They drink tea.", description="Tea")

        response = await client.patch(
            f"{API}/memories/a-fact", json={"text": "They drink tea, black."}
        )

        assert response.status_code == 200
        assert response.json()["text"] == "They drink tea, black."
        assert "They drink tea, black." in services.memories.recall()

    async def test_a_field_left_out_is_left_alone(
        self, client: AsyncClient, services: Services
    ) -> None:
        services.memories.write("a-fact", "They drink tea.", description="Tea", why="They said so")

        await client.patch(f"{API}/memories/a-fact", json={"description": "Hot drinks"})

        item = (await client.get(f"{API}/memories")).json()[0]
        assert (item["text"], item["description"], item["why"]) == (
            "They drink tea.",
            "Hot drinks",
            "They said so",
        )

    async def test_editing_does_not_change_who_wrote_it(
        self, client: AsyncClient, services: Services
    ) -> None:
        """The badge says who *started* the memory. Making it mean who touched it last would turn
        the one interesting thing on that row into a modification timestamp with two values."""
        services.memories.write("a-fact", "They drink tea.", source="auto")

        response = await client.patch(f"{API}/memories/a-fact", json={"text": "They drink coffee."})

        assert response.json()["source"] == "auto"

    async def test_growing_one_past_the_ceiling_is_a_409(
        self, client: AsyncClient, services: Services
    ) -> None:
        services.memories.settings = MemoriesSettings(budget_tokens=40)
        services.memories.write("a-fact", "x" * 100)

        response = await client.patch(f"{API}/memories/a-fact", json={"text": "y" * 400})

        assert response.status_code == 409
        assert "no room" in response.json()["detail"]

    async def test_emptying_one_is_refused_rather_than_leaving_a_blank(
        self, client: AsyncClient, services: Services
    ) -> None:
        services.memories.write("a-fact", "They drink tea.")

        response = await client.patch(f"{API}/memories/a-fact", json={"text": "   "})

        assert response.status_code == 400

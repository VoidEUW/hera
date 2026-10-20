"""A skill can be switched off (#107): the folder stays, the router stops seeing it."""

from __future__ import annotations

from pathlib import Path

import pytest
from core_support import API, WriteSkill
from httpx import AsyncClient

from hera_core.config import load as load_config
from hera_core.config import save as save_config
from hera_core.enabled_skills import EnabledSkillPort, EnabledSkills
from hera_mcp import ToolError
from hera_skillsets import SkillLibrary, SkillRouter


async def _switch(client: AsyncClient, skill_id: str, enabled: bool) -> None:
    response = await client.patch(f"{API}/skills/{skill_id}", json={"enabled": enabled})
    assert response.status_code == 200


class TestTheConfig:
    def test_a_skill_is_switched_off_by_name_and_back_on(self) -> None:
        config = load_config().with_skill_enabled("tdd", False)
        assert config.skills.disabled == ["tdd"]
        assert config.with_skill_enabled("tdd", False).skills.disabled == ["tdd"]
        assert config.with_skill_enabled("tdd", True).skills.disabled == []

    def test_the_list_survives_a_round_trip_and_a_provider_edit(self) -> None:
        save_config(load_config().with_skill_enabled("tdd", False))

        reloaded = load_config()
        assert reloaded.skills.disabled == ["tdd"]

        entry = reloaded.providers[0]
        assert reloaded.with_provider(entry).skills.disabled == ["tdd"]
        assert reloaded.with_timezone("Europe/Berlin").skills.disabled == ["tdd"]
        assert reloaded.activated(entry.name).skills.disabled == ["tdd"]
        assert reloaded.without(entry.name).skills.disabled == ["tdd"]


class TestTheRoute:
    async def test_a_skill_is_on_until_it_is_switched_off(
        self, client: AsyncClient, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd", description="Test first.")

        listed = (await client.get(f"{API}/skills")).json()["skills"]
        assert listed[0]["enabled"] is True

    async def test_switching_one_off_persists_and_keeps_it_listed(
        self, client: AsyncClient, write_skill: WriteSkill, skills_path: Path
    ) -> None:
        write_skill("tdd", description="Test first.")

        response = await client.patch(f"{API}/skills/tdd", json={"enabled": False})

        assert response.status_code == 200
        assert response.json()["enabled"] is False
        assert load_config().skills.disabled == ["tdd"]
        listed = (await client.get(f"{API}/skills")).json()["skills"]
        assert [(skill["id"], skill["enabled"]) for skill in listed] == [("tdd", False)]

        await _switch(client, "tdd", True)
        assert load_config().skills.disabled == []

    async def test_an_unknown_skill_is_a_404(self, client: AsyncClient) -> None:
        response = await client.patch(f"{API}/skills/nope", json={"enabled": False})
        assert response.status_code == 404


class TestWhatTheRouterSees:
    def test_a_switched_off_skill_is_not_retrieved_pinned_or_slashed(
        self, write_skill: WriteSkill, skills_path: Path
    ) -> None:
        write_skill("tdd", description="Write the test first, then the code.")
        library = SkillLibrary(skills_path)
        router = SkillRouter(EnabledSkills(library))
        question = "write the test first then the code"
        assert router.select(question).ids() == ["tdd"]

        save_config(load_config().with_skill_enabled("tdd", False))

        assert router.select(question).ids() == []
        assert router.select(f"/tdd {question}").ids() == []
        assert router.select(question, pinned=["tdd"]).missing == ("tdd",)
        assert router.library.ids() == []
        # The folder is still there, and the unfiltered library still reads it.
        assert library.ids() == ["tdd"]


class TestHeraSkill:
    async def test_a_switched_off_skill_says_so_rather_than_that_it_does_not_exist(
        self, write_skill: WriteSkill, skills_path: Path
    ) -> None:
        write_skill("tdd", description="Test first.")
        port = EnabledSkillPort(SkillLibrary(skills_path))
        assert await port.load("tdd") is not None

        save_config(load_config().with_skill_enabled("tdd", False))

        with pytest.raises(ToolError, match="switched off in Settings"):
            await port.load("tdd")
        assert await port.names() == []
        assert await port.load("nope") is None


class TestTheEditor:
    async def test_the_source_is_read_and_written_back(
        self, client: AsyncClient, write_skill: WriteSkill, skills_path: Path
    ) -> None:
        write_skill("tdd", description="Test first.")

        source = (await client.get(f"{API}/skills/tdd/source")).json()["content"]
        assert source == (skills_path / "tdd" / "SKILL.md").read_text(encoding="utf-8")

        edited = source.replace("Test first.", "Test first, always.")
        response = await client.put(f"{API}/skills/tdd/source", json={"content": edited})

        assert response.status_code == 200
        assert response.json()["description"] == "Test first, always."
        assert (skills_path / "tdd" / "SKILL.md").read_text(encoding="utf-8") == edited

    async def test_a_bad_edit_is_reported_as_problems_not_lost(
        self, client: AsyncClient, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd", description="Test first.")

        response = await client.put(
            f"{API}/skills/tdd/source", json={"content": "---\nname: tdd\n---\nRed, green.\n"}
        )

        assert response.status_code == 200
        assert response.json()["problems"]
        assert [s["id"] for s in (await client.get(f"{API}/skills")).json()["skills"]] == ["tdd"]

    async def test_an_unknown_skill_is_a_404(self, client: AsyncClient) -> None:
        assert (await client.get(f"{API}/skills/nope/source")).status_code == 404
        put = await client.put(f"{API}/skills/nope/source", json={"content": "x"})
        assert put.status_code == 404


class TestAddingAndDeleting:
    async def test_a_whole_file_can_be_created_verbatim(
        self, client: AsyncClient, skills_path: Path
    ) -> None:
        text = "---\nname: note-taking\ndescription: Use when taking notes.\n---\nBe brief.\n"

        response = await client.post(f"{API}/skills", json={"id": "note-taking", "content": text})

        assert response.status_code == 201
        assert (skills_path / "note-taking" / "SKILL.md").read_text(encoding="utf-8") == text

    async def test_deleting_removes_the_folder_and_the_switch(
        self, client: AsyncClient, write_skill: WriteSkill, skills_path: Path
    ) -> None:
        write_skill("tdd", description="Test first.")
        await _switch(client, "tdd", False)

        response = await client.delete(f"{API}/skills/tdd")

        assert response.status_code == 204
        assert not (skills_path / "tdd").exists()
        assert load_config().skills.disabled == []
        assert (await client.get(f"{API}/skills")).json()["skills"] == []

    async def test_deleting_a_linked_skill_keeps_what_it_points_at(
        self, client: AsyncClient, tmp_path: Path, skills_path: Path
    ) -> None:
        elsewhere = tmp_path / "checkout" / "tdd"
        elsewhere.mkdir(parents=True)
        (elsewhere / "SKILL.md").write_text(
            "---\nname: tdd\ndescription: Test first.\n---\nRed.\n", encoding="utf-8"
        )
        skills_path.mkdir(parents=True, exist_ok=True)
        (skills_path / "tdd").symlink_to(elsewhere, target_is_directory=True)

        assert (await client.delete(f"{API}/skills/tdd")).status_code == 204

        assert not (skills_path / "tdd").exists()
        assert (elsewhere / "SKILL.md").is_file()

    async def test_deleting_an_unknown_skill_is_a_404(self, client: AsyncClient) -> None:
        assert (await client.delete(f"{API}/skills/nope")).status_code == 404

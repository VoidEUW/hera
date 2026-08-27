"""What actually reaches the prompt slot, and the usage counts behind the settings screen."""

from __future__ import annotations

from uuid import UUID, uuid4

from skill_support import WriteSkill
from sqlmodel import Session

from hera_skillsets import SkillLibrary, SkillRouter, SkillUsageRepository, render


class TestRendering:
    def test_nothing_selected_renders_as_nothing(self, router: SkillRouter) -> None:
        """An empty string leaves the slot unbound and the section out of the prompt --
        rather than telling the model it has no skills, which is a different sentence."""
        assert render(router.select("hello")) == ""

    def test_a_selected_skill_arrives_in_full(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd", description="Test first.", body="Red.\nGreen.\nRefactor.")

        text = render(router.select("/tdd go"))

        assert "Red.\nGreen.\nRefactor." in text
        assert "Test first." in text

    def test_a_skill_with_no_description_still_renders_its_body(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd", description="", body="Red, green, refactor.")

        text = render(router.select("/tdd go"))

        assert "Red, green, refactor." in text

    def test_the_selected_skills_are_reachable_as_objects(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        assert [skill.id for skill in router.select("/tdd go").skills()] == ["tdd"]

    def test_the_reason_is_said_in_words(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("writing")
        assert "always active" in render(router.select("go", pinned=["writing"]))

    def test_neighbouring_files_are_pointed_at_not_inlined(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd", extra={"mocking.md": "the whole mocking guide"})

        text = render(router.select("/tdd go"))

        assert "mocking.md" in text
        assert "the whole mocking guide" not in text

    def test_the_catalogue_lists_what_was_not_selected(
        self, router: SkillRouter, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        """ADR 5's other half: selection is code, and the model is still told what exists so
        one that does reach for a skill mid-task can call hera__skill."""
        write_skill("tdd")
        write_skill("baking", description="Sourdough bread.")

        text = render(router.select("/tdd go"), catalogue=library.all())

        assert "`baking` — Sourdough bread." in text
        assert "`tdd` —" not in text

    def test_an_empty_catalogue_adds_no_heading(
        self, router: SkillRouter, library: SkillLibrary, write_skill: WriteSkill
    ) -> None:
        write_skill("tdd")
        assert "Other skills installed" not in render(
            router.select("/tdd go"), catalogue=library.all()
        )

    def test_it_emits_no_tags_of_its_own(
        self, router: SkillRouter, write_skill: WriteSkill
    ) -> None:
        """Markdown, not XML: hera_prompts' XML renderer escapes < and >, so anything
        tag-shaped emitted here would reach the model as &lt;tag&gt;."""
        write_skill("tdd", description="Test first.")

        text = render(router.select("/tdd go"))

        assert "<skill" not in text
        assert text.startswith("# Skill: tdd")


class TestUsage:
    def test_a_first_selection_creates_a_row(
        self, usage: SkillUsageRepository, owner_id: UUID
    ) -> None:
        rows = usage.record(owner_id, ["tdd"])
        assert rows[0].hits == 1
        assert rows[0].last_used_at is not None

    def test_selecting_again_counts_up(self, usage: SkillUsageRepository, owner_id: UUID) -> None:
        usage.record(owner_id, ["tdd"])
        usage.record(owner_id, ["tdd"])
        assert usage.for_owner(owner_id)["tdd"].hits == 2

    def test_the_same_skill_twice_in_one_turn_counts_once(
        self, usage: SkillUsageRepository, owner_id: UUID
    ) -> None:
        usage.record(owner_id, ["tdd", "tdd"])
        assert usage.for_owner(owner_id)["tdd"].hits == 1

    def test_recording_nothing_is_harmless(
        self, usage: SkillUsageRepository, owner_id: UUID
    ) -> None:
        assert usage.record(owner_id, []) == []

    def test_counts_are_per_owner(self, usage: SkillUsageRepository) -> None:
        mine, theirs = uuid4(), uuid4()
        usage.record(mine, ["tdd"])
        assert usage.for_owner(theirs) == {}

    def test_forget_removes_the_tally(self, usage: SkillUsageRepository, owner_id: UUID) -> None:
        """A tally, not a record of something that happened -- so a hard delete, not a
        revoke that every later sum has to filter out."""
        usage.record(owner_id, ["tdd"])
        usage.forget(owner_id, "tdd")
        assert usage.for_owner(owner_id) == {}

    def test_forgetting_something_untracked_is_harmless(
        self, usage: SkillUsageRepository, owner_id: UUID
    ) -> None:
        usage.forget(owner_id, "never-used")

    def test_the_table_carries_the_package_prefix(self) -> None:
        from hera_skillsets import SkillUsage

        assert SkillUsage.__tablename__ == "skill_usages"

    def test_a_turns_selections_can_be_recorded_wholesale(
        self,
        usage: SkillUsageRepository,
        router: SkillRouter,
        write_skill: WriteSkill,
        owner_id: UUID,
        session: Session,
    ) -> None:
        write_skill("tdd")
        write_skill("writing")

        routing = router.select("/tdd go", pinned=["writing"])
        usage.record(owner_id, routing.ids())
        session.expire_all()

        assert set(usage.for_owner(owner_id)) == {"tdd", "writing"}

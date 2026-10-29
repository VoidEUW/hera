"""One person's mind over the instance's template (ADR 28)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hera_profiles import (
    SHARED_REGIONS,
    MindRepository,
    PersonalMind,
    PromptBuilder,
    RegionLocked,
    RegionShared,
)


@pytest.fixture
def template(tmp_path: Path) -> MindRepository:
    mind = MindRepository(tmp_path / "template")
    mind.ensure()
    return mind


@pytest.fixture
def ada(tmp_path: Path, template: MindRepository) -> PersonalMind:
    mind = PersonalMind(MindRepository(tmp_path / "users" / "ada" / "mind"), template)
    mind.ensure()
    return mind


def test_a_new_mind_starts_as_the_template_with_its_history(
    template: MindRepository, tmp_path: Path
) -> None:
    template.write("tone", "Warm and brief.")
    mind = PersonalMind(MindRepository(tmp_path / "ben"), template)
    mind.ensure()

    assert mind.read("tone") == "Warm and brief.\n"
    assert mind.own.generation("tone") == 2
    assert mind.own._git("remote") == "", "the clone keeps no way back to the template"


def test_what_a_person_changes_is_theirs_alone(
    ada: PersonalMind, template: MindRepository, tmp_path: Path
) -> None:
    ada.write("tone", "Dry.")
    ben = PersonalMind(MindRepository(tmp_path / "ben"), template)
    ben.ensure()

    assert ada.read("tone") == "Dry.\n"
    assert template.read("tone") != "Dry.\n"
    assert ben.read("tone") == template.read("tone")


def test_the_shared_regions_come_from_the_template_for_everybody(
    ada: PersonalMind, template: MindRepository
) -> None:
    template.write("safety", "Never share a secret.")

    assert ada.read("safety") == "Never share a secret.\n"
    assert ada.generation("safety") == template.generation("safety")
    assert ada.read_all()["safety"] == "Never share a secret.\n"
    assert "Never share a secret." in PromptBuilder(ada).build().render().messages[0].content


@pytest.mark.parametrize("region_id", sorted(SHARED_REGIONS))
def test_a_person_cannot_change_a_shared_region(ada: PersonalMind, region_id: str) -> None:
    with pytest.raises(RegionShared):
        ada.write(region_id, "Anything goes.")
    with pytest.raises(RegionShared):
        ada.propose(region_id, "Anything goes.", origin="dream:1")


def test_about_you_is_owner_fixed_but_the_persons(ada: PersonalMind) -> None:
    """It is about them, so it is theirs to write — and still not a dream's."""
    assert not ada.is_shared("about_you")
    ada.write("about_you", "Ada writes compilers.")
    assert ada.read("about_you") == "Ada writes compilers.\n"
    with pytest.raises(RegionLocked):
        ada.propose("about_you", "Ada writes poems.", origin="dream:1")


def test_a_revert_and_a_show_answer_from_the_right_repository(ada: PersonalMind) -> None:
    first = ada.write("tone", "One.")
    ada.write("tone", "Two.")
    assert first is not None
    assert ada.show("tone", first) == "One.\n"
    ada.revert("tone", first)
    assert ada.read("tone") == "One.\n"
    assert [v.message for v in ada.history("tone", limit=1)] == [f"Revert tone to {first[:8]}"]


def test_ensure_twice_changes_nothing(ada: PersonalMind) -> None:
    before = ada.own.generation("tone")
    ada.ensure()
    assert ada.own.generation("tone") == before


def test_two_first_visits_at_once_make_one_mind(template: MindRepository, tmp_path: Path) -> None:
    """Two repositories over one path, cloning together — two requests, or two processes. One
    rename wins, the other copy is thrown away, and nothing half-cloned is left behind."""
    from concurrent.futures import ThreadPoolExecutor

    target = tmp_path / "users" / "cy" / "mind"
    minds = [PersonalMind(MindRepository(target), template) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda mind: mind.ensure(), minds))

    assert minds[0].own.initialised
    assert sorted(p.name for p in target.parent.iterdir()) == ["mind"]

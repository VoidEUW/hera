"""The registry has to stay internally consistent, and consistent with the layout.

Most of what is checked here would otherwise fail silently: a region nothing renders is a
region a person can edit forever with no effect, and a layout node naming a region that does
not exist is a section that is always empty. Neither raises anything.
"""

from __future__ import annotations

import pytest
from hera_prompts.models import KEY_PATTERN

from hera_profiles import (
    EVOLVABLE_REGIONS,
    LAYOUT_REGIONS,
    LAYOUT_SLOTS,
    MIND_REGIONS,
    SLOTS,
    Tier,
    UnknownRegion,
    filename,
    region,
)


class TestTheRegistry:
    def test_region_ids_are_unique(self) -> None:
        ids = [item.id for item in MIND_REGIONS]
        assert len(ids) == len(set(ids))

    def test_section_keys_are_unique(self) -> None:
        """Two regions rendering into one section would silently overwrite each other."""
        keys = [item.section for item in MIND_REGIONS]
        assert len(keys) == len(set(keys))

    def test_every_section_key_is_addressable_by_hera_prompts(self) -> None:
        for item in MIND_REGIONS:
            assert KEY_PATTERN.match(item.section), item.section

    def test_a_region_id_is_a_safe_file_name(self) -> None:
        for item in MIND_REGIONS:
            assert KEY_PATTERN.match(item.id), item.id
            assert filename(item.id) == f"{item.id}.md"

    def test_every_region_says_what_it_is_for(self) -> None:
        for item in MIND_REGIONS:
            assert item.purpose.strip(), item.id
            assert item.title.strip(), item.id

    def test_the_regions_that_shape_conduct_are_owner_fixed(self) -> None:
        """ADR-level: dreaming must never be able to propose a change to any of these."""
        fixed = {item.id for item in MIND_REGIONS if item.tier is Tier.OWNER_FIXED}
        assert {"about_you", "safety", "developer"} <= fixed

    def test_evolvable_is_the_complement_of_owner_fixed(self) -> None:
        assert set(EVOLVABLE_REGIONS) == {
            item for item in MIND_REGIONS if item.tier is not Tier.OWNER_FIXED
        }

    def test_the_retired_prototype_regions_are_gone(self) -> None:
        """`grammar` described a text call grammar ADR 2 deleted. Shipping it would invite
        the model to use a call syntax nothing in this system parses."""
        assert "grammar" not in {item.id for item in MIND_REGIONS}


class TestLookup:
    def test_a_known_id_returns_its_region(self) -> None:
        assert region("character").title == "Character"

    def test_an_unknown_id_names_what_was_available(self) -> None:
        with pytest.raises(UnknownRegion) as caught:
            region("charakter")
        assert caught.value.region_id == "charakter"
        assert "character" in caught.value.known
        assert "character" in str(caught.value)

    def test_filename_rejects_an_unknown_id_too(self) -> None:
        with pytest.raises(UnknownRegion):
            filename("nonsense")


class TestRegistryAgainstLayout:
    def test_every_region_is_rendered_somewhere(self) -> None:
        unrendered = {item.id for item in MIND_REGIONS} - LAYOUT_REGIONS
        assert not unrendered, f"{sorted(unrendered)} can be edited but will never be read"

    def test_the_layout_names_no_region_that_does_not_exist(self) -> None:
        unknown = LAYOUT_REGIONS - {item.id for item in MIND_REGIONS}
        assert not unknown, f"{sorted(unknown)} would always render empty"

    def test_the_declared_slots_are_exactly_the_ones_the_layout_offers(self) -> None:
        assert SLOTS == LAYOUT_SLOTS

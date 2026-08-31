"""The store: the file format, the key guard, and the ceiling.

What is worth a test here is what a person or a model can get wrong. The format is a contract
with a text editor — somebody will open one of these files and change it — so the tests read and
write real files rather than mocking a filesystem, and several of them assert on the *text* of a
refusal, because that text is what the model gets back and is the only thing it can act on.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from hera_memories import (
    MAX_DESCRIPTION,
    MAX_TEXT,
    MemoriesSettings,
    MemoryFull,
    MemoryRefused,
    MemoryStore,
)


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "memories")


def test_a_memory_is_a_file_you_could_have_written_by_hand(store: MemoryStore) -> None:
    """The format is the export. If this file is not legible, nothing about ADR 16 holds."""
    store.write(
        "runs-models-locally",
        "They run LM Studio on an M-series Mac.",
        description="Runs local models on Apple silicon",
        why="Corrected me after I suggested CUDA flags",
    )

    text = (store.directory / "runs-models-locally.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "description: Runs local models on Apple silicon" in text
    assert "why: Corrected me after I suggested CUDA flags" in text
    assert "enabled: true" in text
    assert text.rstrip().endswith("They run LM Studio on an M-series Mac.")


def test_the_key_is_the_identity_so_writing_twice_corrects(store: MemoryStore) -> None:
    store.write("prefers-short-answers", "They want two sentences.")
    store.write("prefers-short-answers", "They want one sentence.")

    assert len(store.all()) == 1
    memory = store.get("prefers-short-answers")
    assert memory is not None
    assert memory.text == "They want one sentence."


def test_a_correction_keeps_the_date_it_was_first_learned(store: MemoryStore) -> None:
    """An age hint that reset on every rewording would say nothing at all."""
    store.write("a-fact", "First wording.")
    (store.directory / "a-fact.md").write_text(
        "---\ndescription: ''\ncreated: '2020-01-01'\nscope: global\nsource: auto\n"
        "enabled: true\n---\n\nFirst wording.\n",
        encoding="utf-8",
    )

    store.write("a-fact", "Second wording.")

    memory = store.get("a-fact")
    assert memory is not None
    assert memory.created == date(2020, 1, 1)


def test_a_correction_keeps_the_switch_it_had(store: MemoryStore) -> None:
    """Re-remembering something you switched off must not switch it back on and start
    charging you for it again."""
    store.write("a-fact", "First.")
    store.set_enabled("a-fact", False)

    store.write("a-fact", "Second.")

    memory = store.get("a-fact")
    assert memory is not None
    assert memory.enabled is False


@pytest.mark.parametrize(
    "key",
    ["../escape", "with/slash", "Upper", "trailing-", "has space", "", "a" * 65, "."],
)
def test_a_key_that_is_not_a_filename_is_refused(store: MemoryStore, key: str) -> None:
    with pytest.raises(MemoryRefused):
        store.write(key, "Something.")


def test_a_symlink_pointing_out_is_refused_even_though_the_name_is_fine(
    store: MemoryStore, tmp_path: Path
) -> None:
    """The check every string rule reads as an ordinary filename."""
    store.directory.mkdir(parents=True)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (store.directory / "innocent.md").symlink_to(outside / "innocent.md")

    with pytest.raises(MemoryRefused, match="stay inside"):
        store.write("innocent", "Something.")


def test_an_empty_memory_is_refused(store: MemoryStore) -> None:
    with pytest.raises(MemoryRefused, match="needs something in it"):
        store.write("empty", "   \n  ")


def test_a_memory_the_size_of_a_document_is_refused_and_says_where_to_put_it(
    store: MemoryStore,
) -> None:
    with pytest.raises(MemoryRefused, match="artifact"):
        store.write("huge", "x" * (MAX_TEXT + 1))


def test_an_essay_in_the_description_is_refused(store: MemoryStore) -> None:
    with pytest.raises(MemoryRefused, match="description"):
        store.write("a-fact", "Something.", description="x" * (MAX_DESCRIPTION + 1))


def test_a_chat_memory_outside_a_chat_is_refused(store: MemoryStore) -> None:
    with pytest.raises(MemoryRefused, match="not part of a chat"):
        store.write("here-only", "Something.", scope="chat")


class TestTheCeiling:
    @pytest.fixture
    def small(self, tmp_path: Path) -> MemoryStore:
        return MemoryStore(tmp_path / "memories", MemoriesSettings(budget_tokens=40))

    def test_a_write_that_does_not_fit_is_refused_with_what_is_taking_the_space(
        self, small: MemoryStore
    ) -> None:
        """Nothing is dropped to make room, so the refusal has to carry what she needs to make
        room herself — which is the only place anything enumerates memories at her."""
        small.write("first", "x" * 100, description="The first one")

        with pytest.raises(MemoryFull) as raised:
            small.write("second", "y" * 100)

        message = str(raised.value)
        assert "no room" in message
        assert "first (25 tokens): The first one" in message
        assert "forget" in message and "keeps the file" in message

    def test_switching_one_off_gives_the_space_back(self, small: MemoryStore) -> None:
        small.write("first", "x" * 100)
        small.set_enabled("first", False)

        small.write("second", "y" * 100)

        assert small.budget().used == 25
        assert small.budget().disabled == 1

    def test_switching_one_back_on_has_to_fit(self, small: MemoryStore) -> None:
        small.write("first", "x" * 100)
        small.set_enabled("first", False)
        small.write("second", "y" * 100)

        with pytest.raises(MemoryFull):
            small.set_enabled("first", True)

    def test_replacing_a_memory_is_charged_the_difference(self, small: MemoryStore) -> None:
        """Otherwise a store at 95 % could never correct anything it already held."""
        small.write("first", "x" * 150)

        small.write("first", "y" * 150)

        assert small.budget().used == 38

    def test_a_disabled_memory_costs_nothing_and_is_still_there(self, small: MemoryStore) -> None:
        small.write("first", "x" * 100)
        small.set_enabled("first", False)

        assert small.budget().used == 0
        assert small.get("first") is not None
        assert small.recall() == ""


class TestReadingWhatSomebodyWroteByHand:
    """Nothing here raises. A memory a person edited badly is listed with the reason beside
    it, because a Hera that will not start over a stray colon is worse than one memory marked
    broken — the same line `hera_skillsets` holds for a broken SKILL.md."""

    def _put(self, store: MemoryStore, name: str, text: str) -> None:
        store.directory.mkdir(parents=True, exist_ok=True)
        (store.directory / name).write_text(text, encoding="utf-8")

    def test_a_file_with_no_front_matter_is_a_memory_with_no_description(
        self, store: MemoryStore
    ) -> None:
        self._put(store, "plain.md", "They prefer tea.")

        memory = store.get("plain")
        assert memory is not None
        assert memory.text == "They prefer tea."
        assert memory.enabled is True
        assert "no front matter" in memory.problems[0]

    def test_a_hand_written_memory_is_on_by_default(self, store: MemoryStore) -> None:
        """A default of off would make a memory somebody wrote by hand silently do nothing."""
        self._put(store, "plain.md", "They prefer tea.")

        assert store.recall() == "## plain\nThey prefer tea."

    def test_broken_yaml_is_reported_rather_than_raised(self, store: MemoryStore) -> None:
        self._put(store, "odd.md", "---\ndescription: a: b: c\n---\n\nStill readable.\n")

        memory = store.get("odd")
        assert memory is not None
        assert memory.text == "Still readable."
        assert any("not valid YAML" in problem for problem in memory.problems)

    def test_an_unclosed_fence_is_reported(self, store: MemoryStore) -> None:
        self._put(store, "odd.md", "---\ndescription: hi\n\nno closing fence\n")

        memory = store.get("odd")
        assert memory is not None
        assert memory.problems == ("the front-matter fence is never closed",)

    def test_a_date_that_is_not_one_is_reported_and_the_memory_still_works(
        self, store: MemoryStore
    ) -> None:
        self._put(store, "odd.md", "---\ncreated: last tuesday\n---\n\nA fact.\n")

        memory = store.get("odd")
        assert memory is not None
        assert memory.created is None
        assert memory.text == "A fact."
        assert any("not a date" in problem for problem in memory.problems)

    def test_a_scope_nobody_recognises_is_read_as_global(self, store: MemoryStore) -> None:
        self._put(store, "odd.md", "---\nscope: project\n---\n\nA fact.\n")

        memory = store.get("odd")
        assert memory is not None
        assert memory.scope == "global"
        assert any("read as global" in problem for problem in memory.problems)


def test_delete_removes_the_file_and_says_whether_there_was_one(store: MemoryStore) -> None:
    store.write("a-fact", "Something.")

    assert store.delete("a-fact") is True
    assert store.delete("a-fact") is False
    assert store.all() == []


def test_an_empty_directory_is_an_empty_list_rather_than_an_error(store: MemoryStore) -> None:
    assert store.all() == []
    assert store.recall() == ""
    assert store.budget().used == 0


class TestEditing:
    """A person's door, and it is not `write`. That one stores a fact and decides `created`,
    `source` and `enabled` for something that may not exist yet; this one changes what is there
    and decides none of them."""

    def test_the_text_can_be_corrected(self, store: MemoryStore) -> None:
        store.write("a-fact", "They drink tea.", description="Tea")

        store.update("a-fact", text="They drink tea, black, no sugar.")

        memory = store.get("a-fact")
        assert memory is not None
        assert memory.text == "They drink tea, black, no sugar."
        assert memory.description == "Tea"

    def test_a_field_left_out_is_left_alone(self, store: MemoryStore) -> None:
        store.write("a-fact", "They drink tea.", description="Tea", why="They said so")

        store.update("a-fact", description="Hot drinks")

        memory = store.get("a-fact")
        assert memory is not None
        assert (memory.text, memory.description, memory.why) == (
            "They drink tea.",
            "Hot drinks",
            "They said so",
        )

    def test_editing_does_not_change_who_wrote_it(self, store: MemoryStore) -> None:
        """A memory she wrote that you corrected the wording of is still one she wrote. The badge
        says who *started* it; making it mean who touched it last would turn the one interesting
        thing on the row into a modification timestamp with two values."""
        store.write("a-fact", "They drink tea.", source="auto")

        store.update("a-fact", text="They drink coffee.")

        memory = store.get("a-fact")
        assert memory is not None
        assert memory.source == "auto"

    def test_editing_does_not_change_the_date_it_was_learned(self, store: MemoryStore) -> None:
        store.write("a-fact", "First.")
        first = store.get("a-fact")
        assert first is not None

        store.update("a-fact", text="Second.")

        memory = store.get("a-fact")
        assert memory is not None
        assert memory.created == first.created

    def test_growing_one_past_the_ceiling_is_refused(self, tmp_path: Path) -> None:
        small = MemoryStore(tmp_path / "memories", MemoriesSettings(budget_tokens=40))
        small.write("a-fact", "x" * 100)

        with pytest.raises(MemoryFull):
            small.update("a-fact", text="y" * 400)

    def test_shrinking_one_is_always_allowed(self, tmp_path: Path) -> None:
        """Charged the difference rather than the whole, or a store at 95 % could never be
        corrected — which is the state in which correcting one matters most."""
        small = MemoryStore(tmp_path / "memories", MemoriesSettings(budget_tokens=40))
        small.write("a-fact", "x" * 150)

        small.update("a-fact", text="y" * 20)

        assert small.budget().used == 5

    def test_emptying_one_is_refused_rather_than_leaving_a_blank(self, store: MemoryStore) -> None:
        store.write("a-fact", "They drink tea.")

        with pytest.raises(MemoryRefused, match="needs something in it"):
            store.update("a-fact", text="   ")

    def test_editing_one_that_is_not_there_says_so(self, store: MemoryStore) -> None:
        with pytest.raises(MemoryRefused, match="no memory called"):
            store.update("nothing-here", text="x")

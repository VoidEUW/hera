"""What reaches the prompt, and what reaches a file you hand to somebody else.

The two are different on purpose (ADR 16), and the tests that matter are the ones pinning the
difference: metadata that would be paid for in every turn forever stays out of the prompt, and
metadata that makes an export worth having stays in it.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from hera_memories import Memory, MemoryStore, enabled_for, for_export, for_prompt


def a_memory(key: str, text: str = "A fact.", **fields: object) -> Memory:
    return Memory(key=key, text=text, **fields)  # type: ignore[arg-type]


class TestWhatSheReads:
    def test_the_body_and_the_date_and_nothing_else(self) -> None:
        """The date earns its place — it is what lets her tell *this was true in July* from
        *this is true*, and it is the only part of the retrieval design this replaced that
        survives having no retrieval. The description and `why` do not: neither tells the model
        anything the body does not, and both would be in every turn forever."""
        rendered = for_prompt(
            [
                a_memory(
                    "runs-models-locally",
                    "They run LM Studio on an M-series Mac.",
                    description="Runs local models on Apple silicon",
                    why="Corrected me after I suggested CUDA flags",
                    created=date(2026, 8, 31),
                )
            ]
        )

        assert rendered == (
            "## runs-models-locally (2026-08-31)\nThey run LM Studio on an M-series Mac."
        )
        assert "Apple silicon" not in rendered
        assert "CUDA" not in rendered

    def test_a_memory_with_no_date_simply_has_none(self) -> None:
        assert for_prompt([a_memory("plain")]) == "## plain\nA fact."

    def test_nothing_to_recall_is_an_empty_string_rather_than_a_sentence(self) -> None:
        """*You have no memories* is a thing to say to a person. `hera_prompts` already drops a
        section with nothing in it, so an empty slot costs a turn nothing."""
        assert for_prompt([]) == ""

    def test_the_order_is_stable_between_turns(self) -> None:
        """A prompt whose lines move around defeats every caching layer between here and the
        endpoint, and nothing downstream cares what order facts arrive in."""
        memories = [a_memory("zebra"), a_memory("aardvark"), a_memory("moose")]

        assert [memory.key for memory in enabled_for(memories)] == ["aardvark", "moose", "zebra"]


class TestWhichOnesATurnCarries:
    def test_a_disabled_memory_is_not_one_of_them(self) -> None:
        assert enabled_for([a_memory("off", enabled=False)]) == []

    def test_a_chat_memory_belongs_to_its_own_conversation(self) -> None:
        here = a_memory("here", scope="chat", chat_id="abc")
        everywhere = a_memory("everywhere")

        assert enabled_for([here, everywhere], chat_id="abc") == [everywhere, here]
        assert enabled_for([here, everywhere], chat_id="xyz") == [everywhere]
        assert enabled_for([here, everywhere]) == [everywhere]


class TestWhatYouTakeSomewhereElse:
    def test_the_export_is_the_files_verbatim_so_it_can_be_split_back(self, tmp_path: Path) -> None:
        """Lossless is what makes this an export rather than a report. A summary of your
        memories is not something you can take to another tool."""
        store = MemoryStore(tmp_path / "memories")
        store.write("first", "A fact.", description="The first", why="They said so")

        exported = store.export()

        assert "## first" in exported
        assert "description: The first" in exported
        assert "why: They said so" in exported
        assert "A fact." in exported

    def test_a_switched_off_memory_is_still_yours_and_still_exported(self, tmp_path: Path) -> None:
        """The switch is about what a turn costs. A backup that quietly omitted everything you
        had switched off would be the worst kind of surprise to discover from."""
        store = MemoryStore(tmp_path / "memories")
        store.write("kept", "A fact.")
        store.set_enabled("kept", False)

        assert "## kept" in store.export()
        assert store.recall() == ""

    def test_an_export_of_nothing_is_still_a_readable_file(self) -> None:
        assert for_export([]).strip().startswith("<!--")


@pytest.mark.parametrize(
    ("text", "tokens"),
    [("", 0), ("abcd", 1), ("abcde", 2), ("x" * 400, 100)],
)
def test_the_token_estimate_is_the_documented_approximation(text: str, tokens: int) -> None:
    """Four characters to a token, rounded up. Deliberately an approximation: a real count needs
    the endpoint's own tokenizer, which changes when the model does and is not installed — and
    the question the bar answers, *how close am I*, survives being 15 % out."""
    assert a_memory("k", text or "x").tokens == max(tokens, 1)

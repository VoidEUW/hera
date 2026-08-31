"""The async face her tools reach, and the two things it deliberately will not do.

Both absences are the decision rather than an oversight, so both have a test: she cannot list
her memories, because every enabled one is already in her prompt; and she cannot delete one,
because *nothing a person told her is discarded without a person present*.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hera_memories import MemoriesSettings, MemoryFull, MemoryPort, MemoryStore


@pytest.fixture
def port(tmp_path: Path) -> MemoryPort:
    return MemoryPort(MemoryStore(tmp_path / "memories"))


async def test_remembering_says_what_it_cost_and_what_is_left(port: MemoryPort) -> None:
    """The budget travels back in the confirmation, so she can steer without a second call —
    and so the first thing she learns about a full store is not a refusal."""
    answer = await port.remember("a-fact", "They prefer tea.", description="Drinks tea")

    assert "remembered a-fact for good" in answer
    assert "of 4000 left" in answer
    assert port.store.get("a-fact") is not None


async def test_a_chat_memory_says_it_is_only_for_here(port: MemoryPort) -> None:
    answer = await port.remember("here-only", "This branch is a spike.", scope="chat", chat_id="c1")

    assert "for this conversation" in answer
    memory = port.store.get("here-only")
    assert memory is not None
    assert memory.chat_id == "c1"


async def test_forgetting_keeps_the_file_and_says_so(port: MemoryPort) -> None:
    """`forget` is the word the model reaches for, so it is the name — and the confirmation is
    what stops it meaning what the model would assume it means."""
    await port.remember("a-fact", "They prefer tea.")

    answer = await port.forget("a-fact")

    assert "switched off" in answer
    assert "file is kept" in answer
    memory = port.store.get("a-fact")
    assert memory is not None
    assert memory.enabled is False
    assert memory.text == "They prefer tea."


async def test_the_port_offers_no_way_to_delete_anything(port: MemoryPort) -> None:
    """Unlinking is a person on the settings screen and nothing else. The store can do it; the
    face her tools reach cannot."""
    assert not hasattr(port, "delete")
    assert hasattr(port.store, "delete")


async def test_the_port_offers_no_way_to_list_them(port: MemoryPort) -> None:
    """A tool that read her memories back would spend the context window on what is already in
    it — the same reasoning that left `artifact_list` out one milestone earlier."""
    assert not hasattr(port, "all")


async def test_a_full_store_refuses_with_something_she_can_act_on(tmp_path: Path) -> None:
    port = MemoryPort(MemoryStore(tmp_path / "memories", MemoriesSettings(budget_tokens=40)))
    await port.remember("first", "x" * 100, description="The first one")

    with pytest.raises(MemoryFull, match="fold two of these"):
        await port.remember("second", "y" * 100)


async def test_recall_is_what_the_turn_asks_for(port: MemoryPort) -> None:
    await port.remember("everywhere", "A global fact.")
    await port.remember("this-branch", "A local fact.", scope="chat", chat_id="c1")

    assert "everywhere" in await port.recall()
    assert "this-branch" not in await port.recall()
    assert "this-branch" in await port.recall(chat_id="c1")

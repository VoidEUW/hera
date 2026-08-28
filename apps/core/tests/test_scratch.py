"""The scratchpad on disk, and the guard that makes it safe to allow by default.

`hera_mcp` says *she can leave herself working notes*; this module says *they are files, there*
(ADR 12). The name in a write arrives from a model, so most of what is below is about the
difference between a filename and a path — the traversal check gets a class of its own rather
than a comment, because a comment saying the path is validated is not a validation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from hera_core.scratch import MAX_BYTES, MAX_NAME, FileScratchpad, ScratchpadRefused, forget_chat
from hera_home import chat_dir, scratch_dir

CHAT = "0f9c1c2e-1111-4222-8333-444444444444"


@pytest.fixture
def scratchpad() -> FileScratchpad:
    return FileScratchpad()


class TestWritingAndReading:
    async def test_a_write_lands_in_that_conversations_directory(
        self, scratchpad: FileScratchpad
    ) -> None:
        await scratchpad.write(CHAT, "plan.md", "1. read it")

        assert (scratch_dir(CHAT) / "plan.md").read_text() == "1. read it"

    async def test_it_reads_back_what_it_wrote(self, scratchpad: FileScratchpad) -> None:
        await scratchpad.write(CHAT, "plan.md", "1. read it")

        assert await scratchpad.read(CHAT, "plan.md") == "1. read it"

    async def test_a_missing_file_is_none_rather_than_an_error(
        self, scratchpad: FileScratchpad
    ) -> None:
        """Having looked and found nothing is an ordinary answer — the same shape
        `SkillLibrary.load` uses, and the tool turns it into a sentence naming the file."""
        assert await scratchpad.read(CHAT, "gone.md") is None

    async def test_writing_twice_replaces(self, scratchpad: FileScratchpad) -> None:
        await scratchpad.write(CHAT, "plan.md", "first")
        await scratchpad.write(CHAT, "plan.md", "second")

        assert await scratchpad.read(CHAT, "plan.md") == "second"

    async def test_appending_adds(self, scratchpad: FileScratchpad) -> None:
        await scratchpad.write(CHAT, "log.md", "one\n")
        await scratchpad.write(CHAT, "log.md", "two\n", append=True)

        assert await scratchpad.read(CHAT, "log.md") == "one\ntwo\n"

    async def test_appending_to_nothing_creates_it(self, scratchpad: FileScratchpad) -> None:
        """A model that appends first has made a spelling mistake, not an error."""
        await scratchpad.write(CHAT, "log.md", "one\n", append=True)

        assert await scratchpad.read(CHAT, "log.md") == "one\n"

    async def test_two_conversations_do_not_share_a_directory(
        self, scratchpad: FileScratchpad
    ) -> None:
        await scratchpad.write(CHAT, "plan.md", "mine")

        assert await scratchpad.read("another-chat", "plan.md") is None

    async def test_the_confirmation_says_what_happened(self, scratchpad: FileScratchpad) -> None:
        """Read by the model, so it says the name and the size rather than "ok" — which is what
        lets her notice she wrote four bytes when she meant to write four hundred."""
        said = await scratchpad.write(CHAT, "plan.md", "abcd")

        assert said == "wrote plan.md (4 bytes)"


class TestListing:
    async def test_it_names_each_file_with_its_size(self, scratchpad: FileScratchpad) -> None:
        await scratchpad.write(CHAT, "b.md", "xx")
        await scratchpad.write(CHAT, "a.md", "x")

        assert [(f.name, f.size) for f in await scratchpad.files(CHAT)] == [
            ("a.md", 1),
            ("b.md", 2),
        ]

    async def test_a_conversation_that_never_wrote_lists_nothing(
        self, scratchpad: FileScratchpad
    ) -> None:
        assert await scratchpad.files(CHAT) == ()

    async def test_asking_creates_nothing(self, scratchpad: FileScratchpad) -> None:
        """A model asking what it left itself in a fresh conversation should not leave a
        directory behind as a side effect of the question."""
        await scratchpad.files(CHAT)
        await scratchpad.read(CHAT, "plan.md")

        assert not chat_dir(CHAT).exists()

    async def test_a_directory_inside_is_not_listed_as_a_file(
        self, scratchpad: FileScratchpad
    ) -> None:
        """Nothing this package writes makes one, so if one is there it arrived some other way
        and reporting it as a file she can read would be a promise this cannot keep."""
        await scratchpad.write(CHAT, "plan.md", "x")
        (scratch_dir(CHAT) / "sub").mkdir()

        assert [f.name for f in await scratchpad.files(CHAT)] == ["plan.md"]


class TestTheNameGuard:
    """The load-bearing part. These tools are `hera__*`, which `DEFAULT_POLICY` allows without
    a card, and what makes that right is that a name cannot leave the conversation's directory.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "../escape.md",
            "../../../../etc/passwd",
            "sub/plan.md",
            "sub\\plan.md",
            "/etc/passwd",
            ".",
            "..",
        ],
    )
    async def test_a_name_that_is_not_a_plain_filename_is_refused(
        self, scratchpad: FileScratchpad, name: str
    ) -> None:
        with pytest.raises(ScratchpadRefused):
            await scratchpad.write(CHAT, name, "x")

    async def test_nothing_is_written_outside_the_home(
        self, scratchpad: FileScratchpad, tmp_path: Path
    ) -> None:
        """The assertion that matters is not the exception — it is that the file is not there."""
        target = tmp_path / "escaped.md"
        with pytest.raises(ScratchpadRefused):
            await scratchpad.write(CHAT, f"../../../{target.name}", "x")

        assert not target.exists()

    async def test_a_symlink_out_is_refused(
        self, scratchpad: FileScratchpad, tmp_path: Path
    ) -> None:
        """The reason the containment check happens after `resolve` and not on the string. A
        symlink is a traversal that every string check reads as an ordinary filename."""
        outside = tmp_path / "outside.md"
        outside.write_text("theirs")
        scratch_dir(CHAT).mkdir(parents=True)
        (scratch_dir(CHAT) / "link.md").symlink_to(outside)

        with pytest.raises(ScratchpadRefused):
            await scratchpad.write(CHAT, "link.md", "mine")
        assert outside.read_text() == "theirs"

    async def test_reading_through_a_symlink_is_refused_too(
        self, scratchpad: FileScratchpad, tmp_path: Path
    ) -> None:
        """Refusing the write and allowing the read would make the scratchpad a file reader for
        anything a symlink already points at."""
        outside = tmp_path / "outside.md"
        outside.write_text("secret")
        scratch_dir(CHAT).mkdir(parents=True)
        (scratch_dir(CHAT) / "link.md").symlink_to(outside)

        with pytest.raises(ScratchpadRefused):
            await scratchpad.read(CHAT, "link.md")

    async def test_an_empty_name_is_refused(self, scratchpad: FileScratchpad) -> None:
        with pytest.raises(ScratchpadRefused, match="needs a name"):
            await scratchpad.write(CHAT, "   ", "x")

    async def test_a_very_long_name_is_refused_here_rather_than_by_the_filesystem(
        self, scratchpad: FileScratchpad
    ) -> None:
        """An OSError from three frames deeper is not a sentence she can act on."""
        with pytest.raises(ScratchpadRefused, match="too long"):
            await scratchpad.write(CHAT, "x" * (MAX_NAME + 1), "x")

    async def test_a_leading_dot_is_allowed(self, scratchpad: FileScratchpad) -> None:
        """`.notes` is a filename, not a traversal, and refusing every dotted name would be a
        rule about Unix conventions rather than about containment."""
        await scratchpad.write(CHAT, ".notes", "x")

        assert await scratchpad.read(CHAT, ".notes") == "x"


class TestTheSizeCeiling:
    async def test_a_body_over_the_limit_is_refused(self, scratchpad: FileScratchpad) -> None:
        with pytest.raises(ScratchpadRefused, match="limit"):
            await scratchpad.write(CHAT, "big.md", "x" * (MAX_BYTES + 1))

    async def test_appending_past_the_limit_is_refused(self, scratchpad: FileScratchpad) -> None:
        """Counted against what is already there, or a file grows past the ceiling one small
        append at a time — which is the shape a loop actually takes."""
        await scratchpad.write(CHAT, "big.md", "x" * MAX_BYTES)

        with pytest.raises(ScratchpadRefused, match="limit"):
            await scratchpad.write(CHAT, "big.md", "y", append=True)

    async def test_a_refused_write_does_not_truncate_what_was_there(
        self, scratchpad: FileScratchpad
    ) -> None:
        """Checked before the file is opened, because `open("wb")` truncates — so a refusal
        after it would answer *no* and destroy the plan at the same time."""
        await scratchpad.write(CHAT, "plan.md", "the plan")

        with pytest.raises(ScratchpadRefused):
            await scratchpad.write(CHAT, "plan.md", "x" * (MAX_BYTES + 1))
        assert await scratchpad.read(CHAT, "plan.md") == "the plan"


class TestForgetting:
    def test_it_removes_the_whole_directory(self, tmp_path: Path) -> None:
        scratch_dir(CHAT).mkdir(parents=True)
        (scratch_dir(CHAT) / "plan.md").write_text("x")

        forget_chat(CHAT)

        assert not chat_dir(CHAT).exists()

    def test_forgetting_a_chat_that_wrote_nothing_is_fine(self) -> None:
        forget_chat(CHAT)

    def test_an_unusable_id_is_swallowed_rather_than_raised(self) -> None:
        """Called from the delete route. A chat id that is not a path segment cannot reach here
        today, and it is the branch where getting it wrong deletes the wrong tree."""
        forget_chat("../../..")


class TestDeletingAChat:
    async def test_it_takes_the_scratchpad_with_it(self, client: AsyncClient) -> None:
        """ADR 12 calls the scratchpad a cache rather than something a person keeps, so
        cleaning it up is part of deleting the chat rather than a chore for later."""
        chat_id = (await client.post("/api/v1/chats", json={})).json()["id"]
        await FileScratchpad().write(chat_id, "plan.md", "x")
        assert chat_dir(chat_id).exists()

        assert (await client.delete(f"/api/v1/chats/{chat_id}")).status_code == 204

        assert not chat_dir(chat_id).exists()

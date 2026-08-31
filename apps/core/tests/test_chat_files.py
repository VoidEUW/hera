"""What a conversation owns on disk, and the guard that makes both halves safe to allow.

`hera_mcp` says *she can leave herself working notes* (ADR 12) and *she can publish a file*
(ADR 13); this module says *they are files, there*. The name in either arrives from a model, so
most of what is below is about the difference between a filename and a path — the traversal
check gets a class of its own rather than a comment, because a comment saying the path is
validated is not a validation, and it is **parametrised over both adapters** rather than copied,
because a second copy of that guard is the one that quietly stops matching the first.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from httpx import AsyncClient

from hera_core.chat_files import (
    MAX_BYTES,
    MAX_NAME,
    ChatFileRefused,
    FileArtifacts,
    FileScratchpad,
    forget_chat,
)
from hera_home import artifacts_dir, chat_dir, scratch_dir

CHAT = "0f9c1c2e-1111-4222-8333-444444444444"


@pytest.fixture
def scratchpad() -> FileScratchpad:
    return FileScratchpad()


@pytest.fixture
def published() -> FileArtifacts:
    return FileArtifacts()


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


class Both:
    """One of the two directories a conversation owns, behind the two verbs a guard needs.

    The name check is shared code (`_resolve`), so it is tested over both adapters rather than
    once here and once in a copy below — which is the arrangement where the second copy passes
    for a year after the first stopped being run.
    """

    def __init__(
        self,
        where: Path,
        write: Callable[[str, str], Awaitable[object]],
        read: Callable[[str], Awaitable[str | None]],
    ) -> None:
        self.where = where
        self.write = write
        self.read = read


@pytest.fixture(params=["scratchpad", "artifacts"])
def guarded(request: pytest.FixtureRequest) -> Both:
    if request.param == "scratchpad":
        pad = FileScratchpad()
        return Both(
            scratch_dir(CHAT),
            lambda name, text: pad.write(CHAT, name, text),
            lambda name: pad.read(CHAT, name),
        )
    art = FileArtifacts()
    return Both(
        artifacts_dir(CHAT),
        lambda name, text: art.create(CHAT, name, text),
        lambda name: art.read(CHAT, name),
    )


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
        self, guarded: Both, name: str
    ) -> None:
        with pytest.raises(ChatFileRefused):
            await guarded.write(name, "x")

    async def test_nothing_is_written_outside_the_home(self, guarded: Both, tmp_path: Path) -> None:
        """The assertion that matters is not the exception — it is that the file is not there."""
        target = tmp_path / "escaped.md"
        with pytest.raises(ChatFileRefused):
            await guarded.write(f"../../../{target.name}", "x")

        assert not target.exists()

    async def test_a_symlink_out_is_refused(self, guarded: Both, tmp_path: Path) -> None:
        """The reason the containment check happens after `resolve` and not on the string. A
        symlink is a traversal that every string check reads as an ordinary filename."""
        outside = tmp_path / "outside.md"
        outside.write_text("theirs")
        guarded.where.mkdir(parents=True)
        (guarded.where / "link.md").symlink_to(outside)

        with pytest.raises(ChatFileRefused):
            await guarded.write("link.md", "mine")
        assert outside.read_text() == "theirs"

    async def test_reading_through_a_symlink_is_refused_too(
        self, guarded: Both, tmp_path: Path
    ) -> None:
        """Refusing the write and allowing the read would make either directory a file reader
        for anything a symlink already points at."""
        outside = tmp_path / "outside.md"
        outside.write_text("secret")
        guarded.where.mkdir(parents=True)
        (guarded.where / "link.md").symlink_to(outside)

        with pytest.raises(ChatFileRefused):
            await guarded.read("link.md")

    async def test_an_empty_name_is_refused(self, guarded: Both) -> None:
        with pytest.raises(ChatFileRefused, match="needs a name"):
            await guarded.write("   ", "x")

    async def test_a_very_long_name_is_refused_here_rather_than_by_the_filesystem(
        self, guarded: Both
    ) -> None:
        """An OSError from three frames deeper is not a sentence she can act on."""
        with pytest.raises(ChatFileRefused, match="too long"):
            await guarded.write("x" * (MAX_NAME + 1), "x")

    async def test_a_leading_dot_is_allowed(self, guarded: Both) -> None:
        """`.notes` is a filename, not a traversal, and refusing every dotted name would be a
        rule about Unix conventions rather than about containment."""
        await guarded.write(".notes", "x")

        assert await guarded.read(".notes") == "x"

    async def test_the_two_directories_do_not_reach_each_other(
        self, scratchpad: FileScratchpad, published: FileArtifacts
    ) -> None:
        """The reason there are two of them (ADR 13): the scratchpad is somewhere she can think
        out loud unread, and it stops being that the moment a person browses it for the
        deliverable. Same name, two files, and neither tool can see the other's."""
        await scratchpad.write(CHAT, "draft.md", "half an idea")
        await published.create(CHAT, "draft.md", "the finished thing")

        assert await scratchpad.read(CHAT, "draft.md") == "half an idea"
        assert await published.read(CHAT, "draft.md") == "the finished thing"


class TestTheSizeCeiling:
    async def test_a_body_over_the_limit_is_refused(self, scratchpad: FileScratchpad) -> None:
        with pytest.raises(ChatFileRefused, match="limit"):
            await scratchpad.write(CHAT, "big.md", "x" * (MAX_BYTES + 1))

    async def test_appending_past_the_limit_is_refused(self, scratchpad: FileScratchpad) -> None:
        """Counted against what is already there, or a file grows past the ceiling one small
        append at a time — which is the shape a loop actually takes."""
        await scratchpad.write(CHAT, "big.md", "x" * MAX_BYTES)

        with pytest.raises(ChatFileRefused, match="limit"):
            await scratchpad.write(CHAT, "big.md", "y", append=True)

    async def test_a_refused_write_does_not_truncate_what_was_there(
        self, scratchpad: FileScratchpad
    ) -> None:
        """Checked before the file is opened, because `open("wb")` truncates — so a refusal
        after it would answer *no* and destroy the plan at the same time."""
        await scratchpad.write(CHAT, "plan.md", "the plan")

        with pytest.raises(ChatFileRefused):
            await scratchpad.write(CHAT, "plan.md", "x" * (MAX_BYTES + 1))
        assert await scratchpad.read(CHAT, "plan.md") == "the plan"


class TestPublishing:
    """ADR 13. What is different from the scratchpad above: a create replaces rather than
    appends, and an edit is a find-and-replace that has to match exactly once."""

    async def test_a_create_lands_in_the_artifacts_directory(
        self, published: FileArtifacts
    ) -> None:
        await published.create(CHAT, "page.html", "<h1>Hi</h1>")

        assert (artifacts_dir(CHAT) / "page.html").read_text() == "<h1>Hi</h1>"

    async def test_it_answers_with_the_size_it_wrote(self, published: FileArtifacts) -> None:
        """What the tool puts in front of the model, and what a card's byte count is built
        from."""
        assert await published.create(CHAT, "page.html", "abcd") == 4

    async def test_publishing_the_same_name_replaces(self, published: FileArtifacts) -> None:
        """The filename is the identity and nothing is versioned — writing the same name twice
        is what a file does, and the cost is stated in ADR 13 rather than hidden."""
        await published.create(CHAT, "page.html", "first")
        await published.create(CHAT, "page.html", "second")

        assert await published.read(CHAT, "page.html") == "second"

    async def test_an_edit_replaces_one_passage(self, published: FileArtifacts) -> None:
        await published.create(CHAT, "page.html", "<body bg='red'>a long page</body>")

        assert await published.edit(CHAT, "page.html", "red", "brass") == 35
        assert await published.read(CHAT, "page.html") == "<body bg='brass'>a long page</body>"

    async def test_an_edit_that_matches_nothing_says_what_to_do(
        self, published: FileArtifacts
    ) -> None:
        await published.create(CHAT, "page.html", "a long page")

        with pytest.raises(ChatFileRefused, match="artifact_read"):
            await published.edit(CHAT, "page.html", "not in here", "x")

    async def test_an_edit_that_matches_twice_is_refused_with_the_count(
        self, published: FileArtifacts
    ) -> None:
        """A replacement that hit the wrong one of three is a silent corruption, and she cannot
        see the file to notice. The count is in the sentence because it is what tells her how
        much more context to include."""
        await published.create(CHAT, "page.html", "red and red")

        with pytest.raises(ChatFileRefused, match="matches 2 times"):
            await published.edit(CHAT, "page.html", "red", "brass")

    async def test_a_refused_edit_leaves_the_file_alone(self, published: FileArtifacts) -> None:
        await published.create(CHAT, "page.html", "red and red")

        with pytest.raises(ChatFileRefused):
            await published.edit(CHAT, "page.html", "red", "brass")
        assert await published.read(CHAT, "page.html") == "red and red"

    async def test_an_empty_find_is_refused_rather_than_matching_everywhere(
        self, published: FileArtifacts
    ) -> None:
        """``"".count("")`` is the length of the string plus one, so an empty `find` would come
        back as *matches 12 times* — a true sentence about nothing she did."""
        await published.create(CHAT, "page.html", "a long page")

        with pytest.raises(ChatFileRefused, match="`find` is empty"):
            await published.edit(CHAT, "page.html", "", "x")

    async def test_editing_something_never_published_says_so(
        self, published: FileArtifacts
    ) -> None:
        with pytest.raises(ChatFileRefused, match="artifact_create"):
            await published.edit(CHAT, "gone.md", "x", "y")

    async def test_a_body_over_the_limit_is_refused_without_truncating(
        self, published: FileArtifacts
    ) -> None:
        """The same trap the scratchpad recorded: `open("wb")` truncates, so a check after it
        would answer *no* and destroy the published page in the same call."""
        await published.create(CHAT, "page.html", "the page")

        with pytest.raises(ChatFileRefused, match="limit"):
            await published.create(CHAT, "page.html", "x" * (MAX_BYTES + 1))
        assert await published.read(CHAT, "page.html") == "the page"

    async def test_an_edit_that_would_grow_it_past_the_limit_is_refused(
        self, published: FileArtifacts
    ) -> None:
        """The ceiling is about what the file ends up being, not about what the call said —
        a small `replace` can still be the thing that takes a page over it."""
        await published.create(CHAT, "page.html", "x" * (MAX_BYTES - 1) + "R")

        with pytest.raises(ChatFileRefused, match="limit"):
            await published.edit(CHAT, "page.html", "R", "RR")
        assert await published.read(CHAT, "page.html") == "x" * (MAX_BYTES - 1) + "R"

    async def test_asking_creates_nothing(self, published: FileArtifacts) -> None:
        await published.files(CHAT)
        await published.read(CHAT, "page.html")

        assert not chat_dir(CHAT).exists()


class TestListingWhatWasPublished:
    """For the file bar beside the conversation. Deliberately not on the port — a tool that read
    her own filenames back would spend the context window on what is already on screen."""

    async def test_it_names_each_file_with_its_size_and_age(self, published: FileArtifacts) -> None:
        await published.create(CHAT, "page.html", "xx")

        listed = await published.files(CHAT)

        assert [(f.name, f.size) for f in listed] == [("page.html", 2)]
        assert listed[0].modified_at.tzinfo is not None, "a naive timestamp is a bug on the wire"

    async def test_a_conversation_that_published_nothing_lists_nothing(
        self, published: FileArtifacts
    ) -> None:
        assert await published.files(CHAT) == ()

    async def test_the_scratchpad_is_not_in_it(
        self, published: FileArtifacts, scratchpad: FileScratchpad
    ) -> None:
        await scratchpad.write(CHAT, "plan.md", "hers")
        await published.create(CHAT, "page.html", "theirs")

        assert [f.name for f in await published.files(CHAT)] == ["page.html"]


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
    async def test_it_takes_the_scratchpad_and_the_artifacts_with_it(
        self, client: AsyncClient
    ) -> None:
        """ADR 12 calls the scratchpad a cache rather than something a person keeps, so cleaning
        it up is part of deleting the chat rather than a chore for later. ADR 13 puts artifacts
        on the same path deliberately: one cleanup, and the confirmation says how many go with
        it rather than letting somebody find out afterwards."""
        chat_id = (await client.post("/api/v1/chats", json={})).json()["id"]
        await FileScratchpad().write(chat_id, "plan.md", "x")
        await FileArtifacts().create(chat_id, "page.html", "<p>x</p>")
        assert chat_dir(chat_id).exists()

        assert (await client.delete(f"/api/v1/chats/{chat_id}")).status_code == 204

        assert not chat_dir(chat_id).exists()

"""Her scratchpad, as files under ``~/.hera/chats/<chat id>/scratch/``.

The adapter behind :class:`hera_mcp.Scratchpad`, and it lives here for the reason every adapter
does: ``hera_mcp`` says *she can leave herself working notes* and this module says *they are
files, there*. Pointing the scratchpad at object storage, or at a directory a person syncs, is a
class in this module and one line in :mod:`hera_core.wiring`.

**This is where a name is decided to be usable**, which is the load-bearing part
(``docs/adr/0012-a-chat-has-a-scratchpad.md``). The name arrives from a model, so it is checked
rather than trusted: one plain segment, no separators, no ``..``, and the resolved path has to
still be inside the conversation's own directory once symlinks are gone. That last check is why
the comparison happens after :meth:`~pathlib.Path.resolve` and not on the string — a symlink is a
traversal that a string check reads as an ordinary filename.

Everything is synchronous filesystem work run through a worker thread, like
:mod:`hera_core.search`: these are small files, but a slow disk should not stall every other
conversation in the process.
"""

from __future__ import annotations

import asyncio
import shutil
import unicodedata
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from hera_home import chat_dir, scratch_dir
from hera_mcp import ScratchFile

__all__ = ["FileScratchpad", "ScratchpadRefused", "forget_chat"]

MAX_BYTES = 1_000_000
"""The most one scratchpad file may hold.

A ceiling rather than a preference. The scratchpad exists so a turn can put down more than fits
in a tool result; it does not exist so a turn can put down a megabyte and then read it back into
the context window next time. A refusal here is something she can act on — write less, or write
it in pieces — where a silently truncated file is a plan with the end missing.
"""

MAX_NAME = 96
"""How long a filename may be. Generous for `plan.md` and short of what a filesystem refuses,
which is the failure this avoids: a name rejected by the operating system arrives as an OSError
somewhere unhelpful rather than as a sentence she can read."""


class ScratchpadRefused(ValueError):
    """A name or a body the scratchpad will not take.

    Its message is read by the model — the tool wraps it into a ``ToolError`` — so it says what
    was wrong and, where there is one, what to do instead.
    """


class FileScratchpad:
    """One directory per conversation, created on first write and not before.

    Not created on read or on listing, deliberately: a model asking what it left itself in a
    fresh conversation should not leave a directory behind as a side effect of the question.
    """

    async def write(self, chat_id: str, name: str, text: str, *, append: bool = False) -> str:
        return await asyncio.to_thread(self._write, chat_id, name, text, append)

    async def read(self, chat_id: str, name: str) -> str | None:
        return await asyncio.to_thread(self._read, chat_id, name)

    async def files(self, chat_id: str) -> Sequence[ScratchFile]:
        return await asyncio.to_thread(self._files, chat_id)

    # -- the synchronous half ----------------------------------------------------------

    def _write(self, chat_id: str, name: str, text: str, append: bool) -> str:
        target = self._resolve(chat_id, name)
        body = text.encode("utf-8")
        already = target.stat().st_size if append and target.exists() else 0
        if already + len(body) > MAX_BYTES:
            raise ScratchpadRefused(
                f"that would put {name!r} over the {MAX_BYTES} byte limit for one scratchpad "
                "file; write less, or split it across files"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("ab" if append else "wb") as handle:
            handle.write(body)
        verb = "appended to" if append else "wrote"
        return f"{verb} {name} ({target.stat().st_size} bytes)"

    def _read(self, chat_id: str, name: str) -> str | None:
        target = self._resolve(chat_id, name)
        if not target.is_file():
            return None
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError as cause:
            # She wrote text through this tool, so a file that does not decode arrived some
            # other way. Saying so beats handing back replacement characters, which is a lie
            # about the contents in the shape of an answer.
            raise ScratchpadRefused(f"{name!r} is not text this can read back") from cause

    def _files(self, chat_id: str) -> Sequence[ScratchFile]:
        directory = scratch_dir(chat_id)
        if not directory.is_dir():
            return ()
        return tuple(
            ScratchFile(name=entry.name, size=entry.stat().st_size)
            for entry in sorted(directory.iterdir())
            if entry.is_file()
        )

    def _resolve(self, chat_id: str, name: str) -> Path:
        """One usable path inside this conversation's scratchpad, or a refusal.

        The order matters. The cheap string checks come first so that the commonest mistakes get
        the clearest sentences, and the containment check comes last because it is the only one
        that catches a symlink — and it is the one that must not be skippable.
        """
        directory = scratch_dir(chat_id)
        cleaned = unicodedata.normalize("NFC", name).strip()
        if not cleaned:
            raise ScratchpadRefused("a scratchpad file needs a name")
        if len(cleaned) > MAX_NAME:
            raise ScratchpadRefused(
                f"that filename is too long; keep it under {MAX_NAME} characters"
            )
        if cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned or "\0" in cleaned:
            raise ScratchpadRefused(
                f"{name!r} is not a plain filename; the scratchpad is flat, so use something "
                "like `plan.md` with no directories in it"
            )

        target = directory / cleaned
        # `strict=False`, because the ordinary case is a file that does not exist yet. What is
        # being asked is where this path *would* be, with any symlinks along the way followed.
        resolved = target.resolve(strict=False)
        root = directory.resolve(strict=False)
        if resolved != root / cleaned or not resolved.is_relative_to(root):
            raise ScratchpadRefused(f"{name!r} does not stay inside this conversation's scratchpad")
        return resolved


def forget_chat(chat_id: str) -> None:
    """Remove everything a conversation owns on disk.

    Called when a chat is deleted. ADR 12 is explicit that the scratchpad is a cache and not a
    thing a person keeps, so cleaning it up is not optional — leaving it would be a directory
    nobody can reach through the interface, named after a row that no longer exists.

    Failures are swallowed on purpose: a chat that is gone from the database and whose directory
    could not be removed is a stale directory, and turning that into a 500 on the delete button
    would leave the row behind too.
    """
    # `ignore_errors` covers the filesystem; the suppression covers `chat_dir` refusing an id
    # that is not a single path segment. Every caller passes `str(chat.id)`, so that one cannot
    # happen today — and it is the branch where getting it wrong would delete the wrong tree.
    with suppress(ValueError):
        shutil.rmtree(chat_dir(chat_id), ignore_errors=True)

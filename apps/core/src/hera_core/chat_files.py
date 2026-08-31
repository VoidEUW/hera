"""What one conversation owns on disk: her scratchpad, and what she publishes.

The adapters behind :class:`hera_mcp.Scratchpad` and :class:`hera_mcp.Artifacts`, and they live
here for the reason every adapter does: ``hera_mcp`` says *she can leave herself working notes*
and *she can publish a file*, and this module says *they are files, there*. Pointing either at
object storage, or at a directory a person syncs, is a class in this module and one line in
:mod:`hera_core.wiring`.

**One module rather than two**, because there is one chat directory and one name guard
(``docs/adr/0013-an-artifact-is-a-file-she-publishes.md``). Two modules would be two
implementations of the check that makes both tools safe to allow without a permission card, and
the second copy is the one that quietly stops matching the first.

```
~/.hera/chats/<chat id>/
  scratch/      hers. Nobody reads it, and that is a property worth defending (ADR 12)
  artifacts/    what she publishes. Named, rendered, downloadable (ADR 13)
```

**This is where a name is decided to be usable**, which is the load-bearing part. The name
arrives from a model, so it is checked rather than trusted: one plain segment, no separators, no
``..``, and the resolved path has to still be inside the conversation's own directory once
symlinks are gone. That last check is why the comparison happens after
:meth:`~pathlib.Path.resolve` and not on the string — a symlink is a traversal that a string
check reads as an ordinary filename.

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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from hera_home import artifacts_dir, chat_dir, scratch_dir
from hera_mcp import ScratchFile

__all__ = [
    "MAX_BYTES",
    "MAX_NAME",
    "ArtifactFile",
    "ChatFileRefused",
    "FileArtifacts",
    "FileScratchpad",
    "forget_chat",
]

MAX_BYTES = 1_000_000
"""The most one file may hold, on either side.

A ceiling rather than a preference. The scratchpad exists so a turn can put down more than fits
in a tool result; it does not exist so a turn can put down a megabyte and then read it back into
the context window next time. A refusal here is something she can act on — write less, or write
it in pieces — where a silently truncated file is a plan with the end missing, or a page with no
closing tag.
"""

MAX_NAME = 96
"""How long a filename may be. Generous for `plan.md` and short of what a filesystem refuses,
which is the failure this avoids: a name rejected by the operating system arrives as an OSError
somewhere unhelpful rather than as a sentence she can read."""


class ChatFileRefused(ValueError):
    """A name or a body neither directory will take.

    Its message is read by the model — the tool wraps it into a ``ToolError`` — so it says what
    was wrong and, where there is one, what to do instead.
    """


@dataclass(frozen=True, slots=True)
class ArtifactFile:
    """One published artifact, as the file bar beside the conversation shows it.

    Not a :class:`hera_mcp.ScratchFile` with a different name: this one carries ``modified_at``,
    because a person browsing what she made wants to know which is the recent one, and the model
    listing its own scratchpad does not.
    """

    name: str
    size: int
    modified_at: datetime


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
        target = _resolve(scratch_dir(chat_id), name)
        body = text.encode("utf-8")
        already = target.stat().st_size if append and target.exists() else 0
        if already + len(body) > MAX_BYTES:
            raise ChatFileRefused(
                f"that would put {name!r} over the {MAX_BYTES} byte limit for one scratchpad "
                "file; write less, or split it across files"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("ab" if append else "wb") as handle:
            handle.write(body)
        verb = "appended to" if append else "wrote"
        return f"{verb} {name} ({target.stat().st_size} bytes)"

    def _read(self, chat_id: str, name: str) -> str | None:
        return _read_text(_resolve(scratch_dir(chat_id), name), name)

    def _files(self, chat_id: str) -> Sequence[ScratchFile]:
        directory = scratch_dir(chat_id)
        if not directory.is_dir():
            return ()
        return tuple(
            ScratchFile(name=entry.name, size=entry.stat().st_size)
            for entry in sorted(directory.iterdir())
            if entry.is_file()
        )


class FileArtifacts:
    """What she publishes, one directory per conversation (ADR 13).

    The same guard and the same ceiling as the scratchpad above, and two things of its own: a
    create *replaces* rather than appends, because the filename is the identity and writing the
    same name twice is what a file does; and an edit is a find-and-replace that has to match
    exactly once.

    :meth:`files` is here and deliberately **not** on the port. The listing is for the file bar
    beside the conversation — a person's screen — and a tool that read her own filenames back
    into the context window would spend it on something she can already see.
    """

    async def create(self, chat_id: str, name: str, content: str) -> int:
        return await asyncio.to_thread(self._create, chat_id, name, content)

    async def edit(self, chat_id: str, name: str, find: str, replace: str) -> int:
        return await asyncio.to_thread(self._edit, chat_id, name, find, replace)

    async def read(self, chat_id: str, name: str) -> str | None:
        return await asyncio.to_thread(self._read, chat_id, name)

    async def raw(self, chat_id: str, name: str) -> bytes | None:
        """One artifact's bytes, undecoded, or ``None`` if there is no such file.

        For the download route, and only for it. Everything the model touches is text, but a
        download should hand back whatever is on disk rather than refusing a file it cannot
        decode — a person asking to save something wants the file, not an opinion about it.
        """
        return await asyncio.to_thread(self._raw, chat_id, name)

    async def files(self, chat_id: str) -> Sequence[ArtifactFile]:
        return await asyncio.to_thread(self._files, chat_id)

    # -- the synchronous half ----------------------------------------------------------

    def _create(self, chat_id: str, name: str, content: str) -> int:
        target = _resolve(artifacts_dir(chat_id), name)
        body = content.encode("utf-8")
        # Before the file is opened, because `open("wb")` truncates: a refusal after it would
        # answer *no* and destroy the previous version of the page in the same call.
        if len(body) > MAX_BYTES:
            raise ChatFileRefused(
                f"{name!r} is over the {MAX_BYTES} byte limit for one artifact; publish less, "
                "or split it across files"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return len(body)

    def _edit(self, chat_id: str, name: str, find: str, replace: str) -> int:
        target = _resolve(artifacts_dir(chat_id), name)
        if not target.is_file():
            raise ChatFileRefused(
                f"nothing named {name!r} has been published in this conversation; publish it "
                "with `artifact_create` first"
            )
        if not find:
            raise ChatFileRefused(
                "`find` is empty; give the exact text to replace, or publish the file again "
                "with `artifact_create`"
            )
        current = _read_text(target, name) or ""
        # Counted rather than replaced-and-hoped. A replacement that hit the wrong one of three
        # is a silent corruption, and she cannot see the file to notice it happened.
        found = current.count(find)
        if found == 0:
            raise ChatFileRefused(
                f"that text is not in {name}; read it back with `artifact_read` and copy the "
                "passage exactly, whitespace included"
            )
        if found > 1:
            raise ChatFileRefused(
                f"`find` matches {found} times in {name} and it has to match once; include "
                "enough of the surrounding lines to be unique"
            )
        body = current.replace(find, replace, 1).encode("utf-8")
        if len(body) > MAX_BYTES:
            raise ChatFileRefused(
                f"that edit would put {name!r} over the {MAX_BYTES} byte limit for one artifact"
            )
        target.write_bytes(body)
        return len(body)

    def _read(self, chat_id: str, name: str) -> str | None:
        return _read_text(_resolve(artifacts_dir(chat_id), name), name)

    def _raw(self, chat_id: str, name: str) -> bytes | None:
        target = _resolve(artifacts_dir(chat_id), name)
        return target.read_bytes() if target.is_file() else None

    def _files(self, chat_id: str) -> Sequence[ArtifactFile]:
        directory = artifacts_dir(chat_id)
        if not directory.is_dir():
            return ()
        return tuple(
            ArtifactFile(
                name=entry.name,
                size=entry.stat().st_size,
                modified_at=datetime.fromtimestamp(entry.stat().st_mtime, tz=UTC),
            )
            for entry in sorted(directory.iterdir())
            if entry.is_file()
        )


def _resolve(directory: Path, name: str) -> Path:
    """One usable path inside one of a conversation's directories, or a refusal.

    The order matters. The cheap string checks come first so that the commonest mistakes get the
    clearest sentences, and the containment check comes last because it is the only one that
    catches a symlink — and it is the one that must not be skippable.

    Shared by both adapters rather than written twice. These tools are `hera__*`, which
    ``DEFAULT_POLICY`` allows without a permission card, and this function is the entire reason
    that is safe; a second copy of it is a second thing that has to stay right.
    """
    cleaned = unicodedata.normalize("NFC", name).strip()
    if not cleaned:
        raise ChatFileRefused("that needs a name: a plain filename such as `plan.md`")
    if len(cleaned) > MAX_NAME:
        raise ChatFileRefused(f"that filename is too long; keep it under {MAX_NAME} characters")
    if cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned or "\0" in cleaned:
        raise ChatFileRefused(
            f"{name!r} is not a plain filename; these directories are flat, so use something "
            "like `plan.md` with no directories in it"
        )

    target = directory / cleaned
    # `strict=False`, because the ordinary case is a file that does not exist yet. What is being
    # asked is where this path *would* be, with any symlinks along the way followed.
    resolved = target.resolve(strict=False)
    root = directory.resolve(strict=False)
    if resolved != root / cleaned or not resolved.is_relative_to(root):
        raise ChatFileRefused(f"{name!r} does not stay inside this conversation's own directory")
    return resolved


def _read_text(target: Path, name: str) -> str | None:
    """The contents of one file, or ``None`` if there is no such file.

    ``None`` rather than an exception for the same reason ``SkillLibrary.load`` uses it: having
    looked and found nothing is an ordinary answer, and one she should be told plainly enough to
    try a different name.
    """
    if not target.is_file():
        return None
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError as cause:
        # She wrote text through these tools, so a file that does not decode arrived some other
        # way. Saying so beats handing back replacement characters, which is a lie about the
        # contents in the shape of an answer.
        raise ChatFileRefused(f"{name!r} is not text this can read back") from cause


def forget_chat(chat_id: str) -> None:
    """Remove everything a conversation owns on disk.

    Called when a chat is deleted. ADR 12 is explicit that the scratchpad is a cache and not a
    thing a person keeps, so cleaning it up is not optional — leaving it would be a directory
    nobody can reach through the interface, named after a row that no longer exists. Artifacts go
    with it, and ADR 13 accepts that deliberately: one cleanup path, and the confirmation says
    how many go rather than letting a person find out afterwards.

    Failures are swallowed on purpose: a chat that is gone from the database and whose directory
    could not be removed is a stale directory, and turning that into a 500 on the delete button
    would leave the row behind too.
    """
    # `ignore_errors` covers the filesystem; the suppression covers `chat_dir` refusing an id
    # that is not a single path segment. Every caller passes `str(chat.id)`, so that one cannot
    # happen today — and it is the branch where getting it wrong would delete the wrong tree.
    with suppress(ValueError):
        shutil.rmtree(chat_dir(chat_id), ignore_errors=True)

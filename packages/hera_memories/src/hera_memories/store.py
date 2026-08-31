"""The directory of memories, and the ceiling over it.

One file per memory under ``~/.hera/memories/``, and this module is the only thing that turns a
key into a path. The key arrives from a model, so it is checked rather than trusted — the same
argument :mod:`hera_core.chat_files` makes for a chat's directories, and the same shape of
check: cheap string rules first because they give the clearest sentences, containment after
:meth:`~pathlib.Path.resolve` last, because a symlink is a traversal every string rule reads as
an ordinary filename.

**Nothing here raises on bad content.** A memory whose front matter will not parse is listed
with the reason beside it, exactly as a broken ``SKILL.md`` is: a Hera that refuses to start
because a file a person edited has a stray colon in it is worse than a Hera with one memory
marked broken. What *does* raise is a bad **write** — a key that cannot be a filename, or one
more memory than the budget has room for — because those are answers the model needs.

The front-matter split is written out here rather than shared with :mod:`hera_skillsets`, which
has the same twenty lines. That is the layering rule, and it is the right answer for a second
reason: a skill's format is Claude Code's and may not drift, and this one is ours. Sharing them
would tie a decision about Hera's memories to somebody else's release notes.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from hera_memories.models import (
    MAX_DESCRIPTION,
    Budget,
    Memory,
    check_key,
    estimate_tokens,
)
from hera_memories.render import enabled_for, for_export, for_prompt
from hera_memories.settings import MemoriesSettings

FENCE = "---"
SUFFIX = ".md"
MAX_TEXT = 8_000
"""How long one memory may be, in characters.

Well under the budget on purpose: a single memory that fills the ceiling is not a memory, it is
a document, and the thing to do with a document is publish it as an artifact. The refusal says
so rather than letting one write consume everything.
"""


class MemoryRefused(ValueError):
    """A write the store will not take.

    Its message reaches the model through a ``ToolError``, so it says what was wrong and what to
    do instead — a refusal the model cannot act on is a refusal it will simply repeat.
    """


class MemoryFull(MemoryRefused):
    """There is no room left under the ceiling.

    Its own type because the *tool* answers it differently from every other refusal: this is the
    one that asks her to fold two memories into one, and it carries what she needs to do that.
    """


class MemoryStore:
    """Every memory on disk, and what carrying them costs.

    Synchronous, because it is a handful of small files and being synchronous makes it testable
    without a loop. :class:`MemoryPort` is the async face the tools reach it through.
    """

    def __init__(self, directory: Path, settings: MemoriesSettings | None = None) -> None:
        self.directory = directory
        self.settings = settings or MemoriesSettings()

    # -- reading ---------------------------------------------------------------------------

    def all(self) -> list[Memory]:
        """Every memory, newest first, broken ones included and marked.

        Newest first because that is the order the list on screen wants; the *prompt* is sorted
        by key instead, and :func:`hera_memories.render.enabled_for` is what does that.
        """
        if not self.directory.is_dir():
            return []
        found = [self._read(path) for path in sorted(self.directory.glob(f"*{SUFFIX}"))]
        return sorted(found, key=_recency, reverse=True)

    def get(self, key: str) -> Memory | None:
        path = self._resolve(key)
        return self._read(path) if path.is_file() else None

    def raw(self, key: str) -> str | None:
        """The file exactly as it is on disk, for an export that can be split back apart."""
        path = self._resolve(key)
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def budget(self) -> Budget:
        """What the enabled memories cost against the ceiling.

        Over everything enabled rather than over what one turn carries: a person cannot steer by
        a number that changes depending on which conversation is open, and a ceiling that
        over-counts a little errs in the direction a ceiling should.
        """
        memories = self.all()
        enabled = [memory for memory in memories if memory.enabled]
        return Budget(
            used=sum(memory.tokens for memory in enabled),
            limit=self.settings.budget_tokens,
            count=len(enabled),
            disabled=len(memories) - len(enabled),
        )

    def recall(self, *, chat_id: str = "") -> str:
        """The ``memories`` slot for one turn: everything enabled that this chat carries."""
        return for_prompt(enabled_for(self.all(), chat_id=chat_id))

    def export(self) -> str:
        """`MEMORY.md` — every memory, verbatim, in one file."""
        memories = sorted(self.all(), key=lambda memory: memory.key)
        sources = {memory.key: raw for memory in memories if (raw := self.raw(memory.key))}
        return for_export(memories, sources=sources)

    # -- writing ---------------------------------------------------------------------------

    def write(
        self,
        key: str,
        text: str,
        *,
        description: str = "",
        why: str = "",
        scope: str = "global",
        chat_id: str = "",
        source: str = "auto",
    ) -> Memory:
        """Store one memory, replacing any memory with the same key.

        Replacing rather than appending, because the key is the identity: writing
        ``prefers-short-answers`` twice is her correcting herself, and keeping both would leave
        the prompt holding a fact and its replacement with nothing to say which won.

        ``created`` survives a replacement. The date on a memory is when she first learned the
        thing, not when she last touched the file — an age hint that reset every time she
        refined the wording would say nothing at all.
        """
        if problem := check_key(key):
            raise MemoryRefused(problem)
        body = text.strip()
        if not body:
            raise MemoryRefused("a memory needs something in it")
        if len(body) > MAX_TEXT:
            raise MemoryRefused(
                f"that is {len(body)} characters and one memory may be {MAX_TEXT}. "
                "Something this long is a document — publish it as an artifact instead, and "
                "remember the one sentence that says it exists"
            )
        if len(description) > MAX_DESCRIPTION:
            raise MemoryRefused(
                f"the description is {len(description)} characters and the limit is "
                f"{MAX_DESCRIPTION}; it is the one line a person reads in a list"
            )
        if scope == "chat" and not chat_id:
            raise MemoryRefused(
                "a memory scoped to this conversation needs to know which one, and this call "
                "is not part of a chat"
            )

        existing = self.get(key)
        self._afford(body, replacing=existing)

        memory = Memory(
            key=key,
            text=body,
            description=description.strip(),
            why=why.strip(),
            created=existing.created if existing and existing.created else _today(),
            scope="chat" if scope == "chat" else "global",
            chat_id=chat_id if scope == "chat" else "",
            source=source,
            # A replacement keeps the switch it had. Re-remembering something you had switched
            # off should not quietly switch it back on and start charging you for it again.
            enabled=existing.enabled if existing else True,
        )
        self._save(memory)
        return memory

    def update(
        self,
        key: str,
        *,
        text: str | None = None,
        description: str | None = None,
        why: str | None = None,
        enabled: bool | None = None,
    ) -> Memory:
        """Change an existing memory. ``None`` leaves a field alone.

        A person's door, and it is deliberately not :meth:`write`: that one is for *storing a
        fact*, and it decides `created`, `source` and `enabled` for a memory that may not exist
        yet. This one changes what is already there and decides none of them.

        **``source`` does not move.** A memory she wrote that you corrected the wording of is
        still one she wrote — the badge says who *started* it, which is a fact worth keeping.
        Making it mean *who touched it last* would quietly turn the one interesting thing on that
        row into a modification timestamp with two values.

        Growing the text has to fit, the same as any other write, and so does switching one on.
        """
        memory = self.get(key)
        if memory is None:
            raise MemoryRefused(f"there is no memory called {key!r}")

        body = memory.text if text is None else text.strip()
        if not body:
            raise MemoryRefused("a memory needs something in it")
        if len(body) > MAX_TEXT:
            raise MemoryRefused(f"that is {len(body)} characters and one memory may be {MAX_TEXT}")
        wanted = memory.enabled if enabled is None else enabled
        if len(description or "") > MAX_DESCRIPTION:
            raise MemoryRefused(
                f"the description is {len(description or '')} characters and the limit is "
                f"{MAX_DESCRIPTION}"
            )
        if wanted:
            # `replacing` is the memory as it stands only when it is *already* being paid for.
            # Switching one back on has to find room for the whole thing; editing one that is
            # already on is charged the difference, or a store at 95 % could never be corrected.
            self._afford(body, replacing=memory if memory.enabled else None)

        updated = Memory(
            key=memory.key,
            text=body,
            description=memory.description if description is None else description.strip(),
            why=memory.why if why is None else why.strip(),
            created=memory.created,
            scope=memory.scope,
            chat_id=memory.chat_id,
            source=memory.source,
            enabled=wanted,
        )
        self._save(updated)
        return updated

    def set_enabled(self, key: str, enabled: bool) -> Memory:
        """Switch a memory on or off, keeping the file either way.

        The middle option between having something and deleting it, and the reason it exists is
        the ceiling: a memory that is true and rarely relevant should cost nothing and still be
        there. Switching one *on* is a write like any other and has to fit.
        """
        return self.update(key, enabled=enabled)

    def delete(self, key: str) -> bool:
        """Remove the file. A person's decision, never hers — see :class:`MemoryPort`."""
        path = self._resolve(key)
        if not path.is_file():
            return False
        path.unlink()
        return True

    # -- the ceiling -----------------------------------------------------------------------

    def _afford(self, text: str, *, replacing: Memory | None) -> None:
        """Refuse when this write would not fit, with what she needs to make it fit.

        The refusal lists the enabled memories with what each costs, because the answer to a
        full budget is *fold two of these together* and she cannot do that without knowing what
        is there. It is also the only place anything enumerates memories at her — everything
        else is already in her prompt.
        """
        budget = self.budget()
        cost = estimate_tokens(text)
        already = replacing.tokens if replacing is not None and replacing.enabled else 0
        if budget.used - already + cost <= budget.limit:
            return
        listing = "\n".join(
            f"- {memory.key} ({memory.tokens} tokens): {memory.description or _first_line(memory)}"
            for memory in sorted(self.all(), key=lambda memory: memory.tokens, reverse=True)
            if memory.enabled
        )
        raise MemoryFull(
            f"there is no room: {budget.used} of {budget.limit} tokens are in use and this "
            f"one needs {cost}. Nothing is deleted to make space — fold two of these into a "
            "single memory with `remember`, then switch the leftover off with `forget`, which "
            f"keeps the file:\n{listing}"
        )

    # -- the file --------------------------------------------------------------------------

    def _resolve(self, key: str) -> Path:
        """The path for a key, or a refusal.

        Cheap rules first, containment last. ``check_key`` already forbids a separator and a
        dot, so the resolved comparison is belt and braces — and it is what catches the case no
        string rule can: a symlink named like an ordinary memory, pointing at ``config.toml``.
        """
        if problem := check_key(key):
            raise MemoryRefused(problem)
        path = (self.directory / f"{key}{SUFFIX}").resolve(strict=False)
        if not path.is_relative_to(self.directory.resolve(strict=False)):
            raise MemoryRefused(f"{key!r} does not stay inside the memories directory")
        return path

    def _save(self, memory: Memory) -> None:
        front: dict[str, object] = {"description": memory.description}
        if memory.created:
            front["created"] = memory.created.isoformat()
        front["scope"] = memory.scope
        if memory.chat_id:
            front["chat"] = memory.chat_id
        front["source"] = memory.source
        front["enabled"] = memory.enabled
        if memory.why:
            front["why"] = memory.why
        rendered = yaml.safe_dump(front, sort_keys=False, allow_unicode=True).strip()
        path = self._resolve(memory.key)
        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"{FENCE}\n{rendered}\n{FENCE}\n\n{memory.text.strip()}\n", encoding="utf-8"
        )

    def _read(self, path: Path) -> Memory:
        key = path.stem
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return Memory(
                key=key, text="", path=path, enabled=False, problems=(f"unreadable: {exc}",)
            )

        front, body, problems = _split(text)
        created, date_problem = _as_date(front.get("created"))
        if date_problem:
            problems.append(date_problem)
        scope = _as_str(front.get("scope")) or "global"
        if scope not in {"global", "chat"}:
            problems.append(
                f"scope is {scope!r}; it is `global` or `chat`, and this is read as global"
            )
            scope = "global"
        if not body.strip():
            problems.append("nothing under the front matter, so there is nothing to recall")
        return Memory(
            key=key,
            text=body.strip(),
            description=_as_str(front.get("description")),
            why=_as_str(front.get("why")),
            created=created,
            scope=scope,
            chat_id=_as_str(front.get("chat")),
            source=_as_str(front.get("source")) or "manual",
            # A file with no `enabled` is on. Somebody who wrote a memory by hand meant it to
            # count, and a default of off would make a hand-written memory silently do nothing.
            enabled=_as_bool(front.get("enabled"), default=True),
            path=path,
            problems=tuple(problems),
        )


class MemoryPort:
    """The async face :class:`hera_mcp.Memories` describes, over a :class:`MemoryStore`.

    Two methods, because those are the two things *she* may do. Listing is not one of them:
    every enabled memory is already in her prompt, so a tool that read them back would spend the
    context window on what is on screen — the same reasoning that left ``artifact_list`` out one
    milestone earlier. Deleting is not one either: **nothing a person told her is discarded
    without a person present**, so her ``forget`` switches a memory off and keeps the file, and
    the only thing that unlinks anything is a person on the settings screen.

    Threaded, like every other filesystem adapter here: these are small files, but a slow disk
    should not stall every other conversation in the process.
    """

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def remember(
        self,
        key: str,
        text: str,
        *,
        description: str = "",
        why: str = "",
        scope: str = "global",
        chat_id: str = "",
    ) -> str:
        memory = await asyncio.to_thread(
            self.store.write,
            key,
            text,
            description=description,
            why=why,
            scope=scope,
            chat_id=chat_id,
            source="auto",
        )
        budget = await asyncio.to_thread(self.store.budget)
        where = "for this conversation" if memory.scope == "chat" else "for good"
        return (
            f"remembered {memory.key} {where} ({memory.tokens} tokens; "
            f"{budget.left} of {budget.limit} left)"
        )

    async def forget(self, key: str) -> str:
        memory = await asyncio.to_thread(self.store.set_enabled, key, False)
        budget = await asyncio.to_thread(self.store.budget)
        return (
            f"{memory.key} is switched off and will not be in your prompt again. The file is "
            f"kept and a person can switch it back on ({budget.left} of {budget.limit} tokens "
            "free now)"
        )

    async def recall(self, *, chat_id: str = "") -> str:
        return await asyncio.to_thread(self.store.recall, chat_id=chat_id)


# -- reading a file, tolerantly --------------------------------------------------------------


def _split(text: str) -> tuple[dict[str, object], str, list[str]]:
    """Front matter, body, and anything odd about the split."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        # Not an error. A file somebody dropped in with no front matter is a memory with no
        # description and no date, which is a more useful thing to say than "broken".
        return {}, text, ["no front matter, so it has no description or date"]
    for index in range(1, len(lines)):
        if lines[index].strip() == FENCE:
            raw = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            break
    else:
        return {}, text, ["the front-matter fence is never closed"]
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return {}, body, [f"the front matter is not valid YAML ({_one_line(exc)})"]
    if parsed is None:
        return {}, body, []
    if not isinstance(parsed, dict):
        return {}, body, ["the front matter is not a mapping of keys to values"]
    return dict(parsed), body, []


def _as_str(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "no", "off", "0"}
    return default


def _as_date(value: object) -> tuple[date | None, str]:
    """YAML gives a real ``date`` for an unquoted one and a string for a quoted one."""
    if isinstance(value, datetime):
        return value.date(), ""
    if isinstance(value, date):
        return value, ""
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10]), ""
        except ValueError:
            return None, f"created is {value!r}, which is not a date like 2026-08-31"
    return None, ""


def _one_line(exc: object) -> str:
    return " ".join(str(exc).split())


def _first_line(memory: Memory) -> str:
    line = memory.text.strip().splitlines()[0] if memory.text.strip() else ""
    return line if len(line) <= 80 else f"{line[:79]}…"


def _recency(memory: Memory) -> tuple[date, str]:
    return (memory.created or date.min, memory.key)


def _today() -> date:
    """UTC, like everything else stamped in this repository."""
    return datetime.now(UTC).date()

"""What one memory is, and what a set of them costs.

The whole of the format lives here and in :mod:`hera_memories.store`: front matter for the
metadata, markdown under it for the fact. It is `SKILL.md`'s shape on purpose (ADR 5 adopted
Claude Code's unchanged, and ADR 16 adopts that one) — a person who has edited a skill already
knows how to edit a memory, and a file that opens legibly in any editor is what *exportable*
actually means.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
"""Lowercase, digits and single hyphens. The key is the filename, so it is the identity.

The same rule a skill id follows, for the same reason: it has to be a plain path segment on
every filesystem, and it has to be something a person can type when they go looking for the
file. It is also what makes a memory *replaceable* — writing the same key twice is a correction
rather than a second copy of a fact that changed.
"""

MAX_KEY = 64
MAX_DESCRIPTION = 200
"""Where a description stops being one.

It is the line the settings list shows, not the memory — a paragraph here would push the list
into something you scroll instead of scan, and the body is where the detail belongs.
"""

CHARS_PER_TOKEN = 4
"""The approximation the budget is measured in.

Deliberately an approximation and deliberately named. A real count needs the endpoint's own
tokenizer, which changes when the model does, is not installed, and would make the number on
screen depend on which model is selected. Four characters to a token is the usual English
figure; what the bar is for is *how close am I*, and that question survives being 15 % out. The
error is on the safe side for prose and against it for dense punctuation, which is why the
ceiling is not also the context limit.
"""


def estimate_tokens(text: str) -> int:
    """Roughly what ``text`` costs in the prompt. See :data:`CHARS_PER_TOKEN`."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


@dataclass(frozen=True, slots=True)
class Memory:
    """One fact she wrote down, and where it came from.

    ``key`` is the filename without its extension and is not stored inside the file — one place
    for the identity, so renaming the file renames the memory and nothing has to be kept in
    step. Everything else is front matter, except ``text``, which is the body.
    """

    key: str
    text: str
    description: str = ""
    """One line, for the list a person reads. Not injected — see :mod:`hera_memories.render`."""
    why: str = ""
    """What made this worth writing down. Provenance for the person, not for the prompt."""
    created: date | None = None
    scope: str = "global"
    """``global`` or ``chat``. A ``chat`` memory is only carried by the conversation that made
    it; ``chat_id`` says which."""
    chat_id: str = ""
    source: str = "auto"
    """``auto`` when she wrote it, ``manual`` when a person did."""
    enabled: bool = True
    """Whether it is in the prompt. A disabled memory is kept, listed and exported — it just
    costs nothing, which is the whole point of having the switch rather than a delete."""
    path: Path | None = None
    problems: tuple[str, ...] = field(default_factory=tuple)
    """Anything odd about the file, reported rather than raised. A memory nobody can read is
    still a memory somebody wrote, and refusing to start over one stray colon is worse than
    listing it with the reason beside it."""

    @property
    def tokens(self) -> int:
        """What carrying this one costs, measured the way the budget measures it."""
        return estimate_tokens(self.text)

    def belongs_to(self, chat_id: str) -> bool:
        """Whether this memory is carried by that conversation."""
        return self.scope != "chat" or self.chat_id == chat_id


@dataclass(frozen=True, slots=True)
class Budget:
    """How much of the ceiling the enabled memories take.

    Over **everything enabled**, not over what one turn happens to carry. A person cannot steer
    by a number that changes depending on which chat is open, and a ceiling that over-counts
    slightly errs in the direction a ceiling should.
    """

    used: int
    limit: int
    count: int
    """How many memories are enabled."""
    disabled: int
    """How many are kept and switched off. Shown because it is the space already given back."""

    @property
    def left(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def full(self) -> bool:
        return self.used >= self.limit


def check_key(key: str) -> str:
    """The reason ``key`` is not usable, or ``""``.

    A sentence written for the model rather than a boolean, because the model is what gets it
    back: a refusal that says *invalid key* leaves it guessing at which of five rules it broke,
    and it will guess wrong and try again.
    """
    if not key:
        return "a memory needs a key: a short name like `prefers-short-answers`"
    if len(key) > MAX_KEY:
        return f"the key is {len(key)} characters and the limit is {MAX_KEY}"
    if not KEY_PATTERN.match(key):
        return (
            f"{key!r} is not a usable key: lowercase letters, digits and single hyphens, "
            "like `runs-models-locally`"
        )
    return ""

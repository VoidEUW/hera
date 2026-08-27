"""What you have vouched for: ``~/.hera/trusted.json``.

A skill is a folder of instructions that goes into her prompt, and an MCP server is a program
that runs on your machine. Both usually arrive from somewhere else. "Where did this come from,
and is it still what I read?" is a question the settings screen should be able to answer, and
the honest answer needs something outside the skill itself — a skill that declares its own
trustworthiness has declared nothing.

So: a file you write, mapping an identifier to the SHA-256 of the content you accepted.

```json
{ "skills": { "tdd": "9f2c…" } }
```

Three verdicts follow from it, and the middle one is the reason this is a digest rather than a
list of names:

- **verified** — listed, and the content still hashes to what you listed.
- **modified** — listed, and it does not. Somebody edited it after you accepted it, which is
  worth saying loudly; a plain "not verified" would read as "you never signed this one".
- **unknown** — not listed. The ordinary state, and not a complaint: nothing is verified on a
  fresh install and the screen should not look alarming because of it.

No file means every verdict is *unknown*. That is the default and it is deliberate: this is a
seam for a signed registry — one this project's owner intends to publish — and a seam that
invents trust before the registry exists would be worse than no seam at all.

Sitting in ``apps/core`` rather than in ``hera_skillsets`` is the layering answer to one file
covering two packages: skills are content on disk and servers are processes, neither package
may import the other, and a copy of this in each would be two files that can disagree about who
you trust. The library computes the digest, because it is holding the bytes. This decides what
the digest means.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from hera_home import home

TRUST_FILENAME = "trusted.json"

Verdict = Literal["verified", "modified", "unknown"]


class TrustError(Exception):
    """The file exists and could not be read. Reported next to the list, never raised at a
    person as a failed screen — a typo in a JSON file must not be able to hide every skill you
    have."""


class Trust(BaseModel):
    """The registry, as loaded."""

    model_config = ConfigDict(frozen=True)

    skills: dict[str, str] = Field(default_factory=dict)
    """Skill directory name → SHA-256 of its ``SKILL.md``."""

    servers: dict[str, str] = Field(default_factory=dict)
    """Reserved for MCP servers, which have no digest yet. Read so that a file carrying them is
    not rejected, and not consulted by anything."""

    def skill(self, skill_id: str, digest: str) -> Verdict:
        """What to say about one skill."""
        expected = self.skills.get(skill_id)
        if expected is None:
            return "unknown"
        return "verified" if digest and digest == expected else "modified"


EMPTY = Trust()


def trust_path() -> Path:
    return home() / TRUST_FILENAME


def load(path: Path | None = None) -> Trust:
    """Read the registry. A missing file is an empty one; a broken file is a `TrustError`."""
    source = path or trust_path()
    if not source.is_file():
        return EMPTY
    try:
        parsed = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustError(f"{source} could not be read: {exc}") from exc
    if not isinstance(parsed, dict):
        raise TrustError(f"{source} should hold an object with a 'skills' key")
    try:
        return Trust.model_validate(parsed)
    except ValueError as exc:
        raise TrustError(f"{source} is not shaped like a trust list: {exc}") from exc

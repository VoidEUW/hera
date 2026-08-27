"""Reading a ``SKILL.md`` off disk.

The format is Claude Code's and is adopted unchanged (ADR 5): YAML frontmatter between two
``---`` fences, then Markdown. Skills are portable in both directions — the same directory can
be pointed at by Claude Code — so anything this module *required* that Claude Code does not
would quietly break that.

Nothing here raises for bad content. A person editing a skill gets it listed with the reason
next to it, because a Hera that refuses to start over a stray colon in someone's YAML is worse
than a Hera with one skill marked broken.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import yaml

from hera_skillsets.models import ID_PATTERN, SKILL_FILENAME, BrokenSkill, Skill

FENCE = "---"
MAX_DESCRIPTION = 1024
"""Where a description stops being a description.

ADR 5 retrieves on this field, and a whole essay pasted into it matches everything. The limit
is a reported problem rather than a truncation: the author should shorten it, and silently
using the first kilobyte would hide why retrieval went strange.
"""


def load_skill(directory: Path) -> Skill | BrokenSkill:
    """Read one skill directory.

    Returns a :class:`~hera_skillsets.models.BrokenSkill` when there is nothing usable to read
    at all, and a :class:`~hera_skillsets.models.Skill` carrying ``problems`` when the file is
    readable but says something odd.
    """
    skill_id = directory.name
    source = directory / SKILL_FILENAME
    if not source.is_file():
        return BrokenSkill(id=skill_id, path=directory, reason=f"no {SKILL_FILENAME} in it")
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return BrokenSkill(id=skill_id, path=directory, reason=f"unreadable: {exc}")

    frontmatter, body, problems = _split(text)
    problems.extend(_check_id(skill_id))

    name = _string(frontmatter.pop("name", "")) or skill_id
    if name != skill_id and ID_PATTERN.match(skill_id):
        problems.append(
            f"the frontmatter calls this {name!r} but the directory is {skill_id!r}; "
            f"the directory wins, so /{skill_id} is what invokes it"
        )

    description = _string(frontmatter.pop("description", ""))
    if not description:
        problems.append(
            "no description, so retrieval can never select it — it will only ever arrive "
            "pinned or by /slash"
        )
    elif len(description) > MAX_DESCRIPTION:
        problems.append(
            f"the description is {len(description)} characters; a description that long "
            "matches everything, which is the same as matching nothing"
        )

    if not body.strip():
        problems.append("nothing below the frontmatter, so there is nothing to inject")

    return Skill(
        id=skill_id,
        name=name,
        description=description,
        body=body.strip(),
        path=directory,
        resources=_resources(directory),
        metadata={key: _string(value) for key, value in frontmatter.items()},
        digest=sha256(text.encode("utf-8")).hexdigest(),
        problems=tuple(problems),
    )


def _split(text: str) -> tuple[dict[str, object], str, list[str]]:
    """Frontmatter, body, and anything odd about the split.

    A file with no frontmatter is not an error — it is a skill with no description, which is
    a different and more useful complaint.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return {}, text, ["no YAML frontmatter, so it has no name or description"]

    for index in range(1, len(lines)):
        if lines[index].strip() == FENCE:
            raw = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            break
    else:
        return {}, text, ["the frontmatter fence is never closed"]

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return (
            _salvage(raw),
            body,
            [
                f"the frontmatter is not valid YAML ({_one_line(exc)}), so it was read line "
                "by line instead — quote any value containing a colon"
            ],
        )
    if parsed is None:
        return {}, body, ["the frontmatter is empty"]
    if not isinstance(parsed, dict):
        return {}, body, ["the frontmatter is not a mapping of keys to values"]
    return dict(parsed), body, []


def _salvage(raw: str) -> dict[str, object]:
    """Read frontmatter as plain ``key: value`` lines when YAML has refused it.

    Worth the twenty lines because of one specific, common mistake: ``description: Use when:
    you need X``. That is a natural sentence and invalid YAML — a plain scalar may not contain
    ``": "`` — and PyYAML rejects the *whole* block over it. Without a fallback the skill loses
    its description, silently becomes unretrievable, and the author has no way to tell from the
    outside that a colon was the reason.

    Splits on the first ``": "`` only, so everything after it stays in the value. Continuation
    lines and anything nested are dropped; this is a rescue, not a second YAML implementation,
    and the reported problem tells the author to quote the value.
    """
    salvaged: dict[str, object] = {}
    for line in raw.splitlines():
        if not line.strip() or line.startswith((" ", "\t", "#", "-")):
            continue
        key, separator, value = line.partition(":")
        if not separator or not key.strip():
            continue
        salvaged[key.strip()] = value.strip().strip("\"'")
    return salvaged


def _check_id(skill_id: str) -> list[str]:
    if ID_PATTERN.match(skill_id):
        return []
    return [
        f"{skill_id!r} is not a usable directory name — lowercase letters, digits and "
        "hyphens only, which is what Claude Code accepts too"
    ]


def _resources(directory: Path) -> tuple[str, ...]:
    """Everything in the directory except the skill file itself, sorted.

    Directories come back with a trailing slash rather than being walked. A skill's body is
    what says which of these matter; listing every file inside `references/` would be noise
    on a settings screen and tokens in a prompt.
    """
    found: list[str] = []
    for entry in directory.iterdir():
        if entry.name == SKILL_FILENAME or entry.name.startswith("."):
            continue
        found.append(f"{entry.name}/" if entry.is_dir() else entry.name)
    return tuple(sorted(found))


def _string(value: object) -> str:
    """Frontmatter values are whatever YAML decided. Everything here is read as text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _one_line(exc: Exception) -> str:
    return " ".join(str(exc).split())

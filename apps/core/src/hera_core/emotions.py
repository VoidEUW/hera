"""``~/.hera/emotions.json`` — the stances she can show, as the person has them.

`hera_mcp` owns what an emotion *is* and ships the fourteen she starts with. This owns where
the person's own list lives, which is a file they can read, diff, copy to another machine, and
put back with one button.

Missing file means the defaults, and that is not a placeholder: nothing is written until
something is changed, so a fresh install has no file and behaves exactly like one that saved
the defaults. A file that will not parse is a reported problem rather than an exception — the
list on screen falls back to the defaults and says why, because a typo in a JSON file must not
be able to leave her with no vocabulary mid-conversation.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hera_home import home
from hera_mcp import DEFAULT_EMOTIONS, Emotion

EMOTIONS_FILENAME = "emotions.json"


class EmotionsError(Exception):
    """The file exists and could not be read."""


class Emotions(BaseModel):
    """The list as stored."""

    model_config = ConfigDict(frozen=True)

    emotions: list[Emotion] = Field(default_factory=lambda: list(DEFAULT_EMOTIONS))


def emotions_path() -> Path:
    return home() / EMOTIONS_FILENAME


def load(path: Path | None = None) -> list[Emotion]:
    """The person's vocabulary, or the one she ships with."""
    source = path or emotions_path()
    if not source.is_file():
        return list(DEFAULT_EMOTIONS)
    try:
        parsed = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EmotionsError(f"{source} could not be read: {exc}") from exc
    try:
        return list(Emotions.model_validate(parsed).emotions)
    except ValidationError as exc:
        raise EmotionsError(f"{source} is not a list of emotions: {exc}") from exc


def save(emotions: list[Emotion], path: Path | None = None) -> list[Emotion]:
    """Write the list whole, replacing atomically.

    Whole rather than patched: the order is part of what a person edited, and a half-written
    file is a vocabulary that fails to parse on the next turn.
    """
    target = path or emotions_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    body = Emotions(emotions=emotions).model_dump_json(indent=2)
    temporary = target.with_suffix(f"{target.suffix}.writing")
    temporary.write_text(f"{body}\n", encoding="utf-8")
    temporary.replace(target)
    return emotions


def reset(path: Path | None = None) -> list[Emotion]:
    """Put the shipped vocabulary back by deleting the file rather than rewriting it.

    Then "reset" and "never touched" are the same state on disk, and a later change to the
    defaults reaches somebody who reset rather than being frozen at whatever this version's
    list happened to be.
    """
    target = path or emotions_path()
    target.unlink(missing_ok=True)
    return list(DEFAULT_EMOTIONS)

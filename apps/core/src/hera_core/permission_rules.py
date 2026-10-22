"""The rules a person made or answered, kept across restarts.

``hera_permissions`` is pure policy over names and does no I/O, so this is where a rule meets a
file (#109). ``~/.hera/permissions.json`` holds what the person decided — **not** a copy of the
rules Hera ships with — and is laid over the built-in policy at boot, which is the same bargain
``config.toml`` makes: the file means *what I decided*, not *what the defaults were the day I
installed it*. A default this project later improves reaches everybody who has not overridden it.

Three kinds of rule come out of it and the screen tells them apart:

* **default** — shipped with Hera. It can be changed (the change is a rule of the person's own,
  on the same pattern) but not removed; deleting the override puts the default back.
* **you** — made on the screen.
* **card** — made by answering "always" on a confirmation card, named automatically and marked
  as coming from a card, so a person can find the ones they did not write by hand.

Everything here is read-modify-write under one lock: two requests changing rules at once must not
lose one of them, and the file is replaced atomically so a crash never leaves half of one.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hera_home import permissions_path
from hera_permissions import Decision, Policy, Rule

__all__ = [
    "PermissionsFileError",
    "RuleSource",
    "StoredPermissions",
    "StoredRule",
    "apply",
    "card_name",
    "load",
    "save",
]

RuleSource = Literal["default", "you", "card"]

LOCK = threading.Lock()
"""Held around every read-modify-write of the file, by the module that does one."""


class PermissionsFileError(RuntimeError):
    """``permissions.json`` exists and cannot be used. Said at boot, with the path, rather than
    ignored: an ignored file is rules a person wrote that silently stopped applying."""


class StoredRule(BaseModel):
    """One rule as it is written down, and where it came from."""

    model_config = ConfigDict(frozen=True)

    pattern: str
    decision: Decision
    reason: str = ""
    name: str = ""
    source: Literal["you", "card"] = "you"

    def rule(self) -> Rule:
        return Rule(
            pattern=self.pattern, decision=self.decision, reason=self.reason, name=self.name
        )


class StoredPermissions(BaseModel):
    """The whole file: the person's rules, and the fallback if they changed it."""

    model_config = ConfigDict(frozen=True)

    fallback: Decision | None = None
    """``None`` means *not changed*: the built-in fallback applies, and keeps applying if a later
    version improves it."""
    rules: list[StoredRule] = Field(default_factory=list)

    def with_rule(self, stored: StoredRule) -> StoredPermissions:
        kept = [existing for existing in self.rules if existing.pattern != stored.pattern]
        return self.model_copy(update={"rules": [*kept, stored]})

    def without(self, pattern: str) -> StoredPermissions:
        return self.model_copy(
            update={"rules": [rule for rule in self.rules if rule.pattern != pattern]}
        )

    def get(self, pattern: str) -> StoredRule | None:
        return next((rule for rule in self.rules if rule.pattern == pattern), None)


def apply(base: Policy, stored: StoredPermissions) -> Policy:
    """The policy in force: the built-in one with the person's rules laid over it."""
    policy = base
    for item in stored.rules:
        policy = policy.with_rule(item.rule())
    if stored.fallback is not None:
        policy = policy.with_fallback(stored.fallback)
    return policy


def card_name(tools: Sequence[str], *, allow: bool) -> str:
    """What a rule made from a card answer is called: *Allowed from a card · fs read_file*."""
    verb = "Allowed" if allow else "Denied"
    return f"{verb} from a card · " + ", ".join(tool.replace("__", " ", 1) for tool in tools)


def load(path: Path | None = None) -> StoredPermissions:
    """Read the file. Nothing there yet is an empty set, not an error."""
    path = path if path is not None else permissions_path()
    if not path.is_file():
        return StoredPermissions()
    try:
        return StoredPermissions.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as cause:
        raise PermissionsFileError(f"{path} could not be used: {cause}") from cause


def save(stored: StoredPermissions, path: Path | None = None) -> None:
    """Write the file whole and replace it atomically, sorted so a diff of it reads."""
    path = path if path is not None else permissions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = stored.model_copy(
        update={"rules": sorted(stored.rules, key=lambda rule: rule.pattern)}
    ).model_dump(mode="json", exclude_defaults=False)
    temporary = path.with_suffix(f"{path.suffix}.writing")
    temporary.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)

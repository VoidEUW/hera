"""What this package raises — which is very little, deliberately.

A malformed skill is not an exception. Someone editing a `SKILL.md` in their vault should get
a broken skill listed on the settings screen with the reason next to it, not a Hera that
refuses to boot. Loading therefore reports problems as data; only a caller asking for a skill
by name and getting it wrong raises.
"""

from __future__ import annotations

from collections.abc import Sequence


class SkillsError(Exception):
    """Base class for every error raised by ``hera_skillsets``."""


class UnknownSkill(SkillsError):
    """A skill was asked for by name and there is no such skill.

    Only raised where the caller has no way to carry on: ``SkillLibrary.get`` returns ``None``
    and the router reports a missing name in ``Routing.missing``, because in both of those the
    right answer is to say so and continue.
    """

    def __init__(self, skill_id: str, known: Sequence[str]) -> None:
        self.skill_id = skill_id
        self.known = list(known)
        listed = ", ".join(self.known) if self.known else "none installed"
        super().__init__(f"unknown skill {skill_id!r}; available: {listed}")

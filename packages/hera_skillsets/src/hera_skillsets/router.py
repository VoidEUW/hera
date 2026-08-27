"""Choosing the skills for a turn — in code, before the model sees anything.

This is ADR 5. The target model does not reliably notice that a skill applies, and a mechanism
that only works when the model volunteers is not a mechanism. So selection happens here, in
three passes, and the model is told what it got rather than asked what it wants:

1. **Pinned** — attached to the profile or the project. No judgment involved.
2. **Explicit** — a ``/skill-name`` typed in the composer, resolved and stripped from the text.
3. **Retrieved** — scored against each skill's ``description``, above a floor, under a cap.

Every selection carries **why** it was chosen. That is not decoration: ``docs/frontend.md``
draws the activity gutter showing "she always has this" separately from "she went and found
this", and it is the only feedback loop that tells you retrieval is picking the wrong thing.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from hera_skillsets.library import SkillLibrary
from hera_skillsets.models import Skill
from hera_skillsets.retrieval import Embedder, keyword_scores

SLASH = re.compile(r"(?:(?<=\s)|^)/([a-z0-9][a-z0-9-]*)(?=\s|$)")
"""A ``/skill-name`` anywhere a word can start.

Anchored to whitespace so a URL path, a date and ``and/or`` are not commands. Unanchored
matching here would make every message containing a slash a lottery.
"""

DEFAULT_LIMIT = 2
"""How many skills retrieval may add on its own.

ADR 5 says one or two full skills is not a problem for a 35B context, and two is the number at
which a wrong guess still leaves room for the right one.
"""

DEFAULT_FLOOR = 0.25
"""How well a description has to match before it is worth the tokens.

Set so that an unrelated turn selects nothing at all. Selecting the least-bad skill for every
message is the failure mode that makes people stop trusting the gutter.
"""

DEFAULT_BUDGET_CHARS = 24_000
"""Roughly how much skill text one turn may carry, counted in characters.

Characters rather than tokens because this package may not import ``hera_prompts``, which owns
the estimator — see the layering table in ARCHITECTURE.md. The ratio is about four characters
to a token either way, and the cap is a guard rail rather than an accountant: the real budget
is enforced by ``hera_prompts`` at render time, which drops sections it cannot fit and says
which in ``dropped_keys``.
"""


class Reason(StrEnum):
    """Why a skill is in this turn."""

    PINNED = "pinned"
    SLASH = "slash"
    RETRIEVED = "retrieved"


class Selection(BaseModel):
    """One skill and the reason it was chosen."""

    model_config = ConfigDict(frozen=True)

    skill: Skill
    reason: Reason
    score: float | None = None
    """The retrieval score, for a retrieved skill only. Shown in the gutter, and the number
    to look at when retrieval selects something strange."""


class Routing(BaseModel):
    """Everything the turn needs to know about skills."""

    model_config = ConfigDict(frozen=True)

    selections: tuple[Selection, ...] = ()
    text: str = ""
    """The user's message with its ``/commands`` removed.

    Stripped because the command is addressed to Hera-the-application, not to her. Leaving
    ``/tdd`` in front of the question makes the model answer about the token.
    """

    missing: tuple[str, ...] = ()
    """Names that were asked for and do not exist — a dangling pin, or a mistyped slash.

    Reported rather than raised. A stale pin should show up on the settings screen and in the
    gutter, and it must not stop the turn.
    """

    dropped: tuple[str, ...] = Field(default=())
    """Skills that were selected and then left out because the budget ran out.

    Kept apart from ``missing``: one is a skill that is gone and the other is a skill that is
    there and did not fit, and the fixes are completely different.
    """

    def skills(self) -> list[Skill]:
        return [selection.skill for selection in self.selections]

    def ids(self) -> list[str]:
        return [selection.skill.id for selection in self.selections]


class SkillRouter:
    """Picks the skills for a turn. Never asks the model.

    Stateless apart from the library it reads and the embedder it may have been given, so one
    instance serves every turn.
    """

    def __init__(
        self,
        library: SkillLibrary,
        *,
        embedder: Embedder | None = None,
        limit: int = DEFAULT_LIMIT,
        floor: float = DEFAULT_FLOOR,
        budget_chars: int = DEFAULT_BUDGET_CHARS,
    ) -> None:
        self.library = library
        self.embedder = embedder
        self.limit = limit
        self.floor = floor
        self.budget_chars = budget_chars

    def select(self, text: str, *, pinned: Sequence[str] = ()) -> Routing:
        """The skills for one turn.

        ``pinned`` is the profile's and the project's pins together, already merged by the
        caller — this package knows what a skill is and deliberately not what a profile or a
        project is.
        """
        cleaned, requested = self._split_commands(text)

        chosen: dict[str, Selection] = {}
        missing: list[str] = []

        # Order matters twice over: it decides which skills survive the budget, and it decides
        # which reason a skill selected twice is shown with. Pinned outranks slash because
        # "she always has this" is the truer sentence when both apply.
        for names, reason in ((pinned, Reason.PINNED), (requested, Reason.SLASH)):
            found, absent = self.library.resolve(names)
            missing.extend(absent)
            for skill in found:
                chosen.setdefault(skill.id, Selection(skill=skill, reason=reason))

        for skill, score in self._retrieve(cleaned, exclude=set(chosen)):
            chosen[skill.id] = Selection(skill=skill, reason=Reason.RETRIEVED, score=score)

        selections, dropped = self._fit(list(chosen.values()))
        return Routing(
            selections=tuple(selections),
            text=cleaned,
            missing=tuple(dict.fromkeys(missing)),
            dropped=tuple(dropped),
        )

    def _split_commands(self, text: str) -> tuple[str, list[str]]:
        """The message without its commands, and the commands in the order they appeared."""
        requested = list(dict.fromkeys(SLASH.findall(text)))
        if not requested:
            return text.strip(), []
        cleaned = SLASH.sub("", text)
        return re.sub(r"[ \t]{2,}", " ", cleaned).strip(), requested

    def _retrieve(self, text: str, *, exclude: set[str]) -> list[tuple[Skill, float]]:
        """Skills whose description matches the turn well enough to be worth the tokens."""
        if self.limit <= 0 or not text.strip():
            return []
        candidates = [
            skill
            for skill in self.library.all()
            if skill.id not in exclude and skill.usable and skill.description
        ]
        if not candidates:
            return []

        descriptions = [f"{skill.name} {skill.description}" for skill in candidates]
        scores = self._score(text, descriptions)

        ranked = sorted(
            ((skill, score) for skill, score in zip(candidates, scores, strict=True)),
            # Ties break on id, so two equally good skills always come out in the same order
            # and the gutter does not shuffle between identical turns.
            key=lambda pair: (-pair[1], pair[0].id),
        )
        return [pair for pair in ranked if pair[1] >= self.floor][: self.limit]

    def _score(self, text: str, descriptions: Sequence[str]) -> Sequence[float]:
        """Embeddings when they are wired, rarity-weighted overlap when they are not.

        An embedder that fails is treated as an embedder that is absent. A model endpoint
        being down must not mean skills silently stop arriving — that looks identical to
        skills not being relevant, which is the one confusion this whole ADR exists to avoid.
        """
        if self.embedder is None:
            return keyword_scores(text, descriptions)
        try:
            scored = self.embedder.similarity(text, descriptions)
        except Exception:
            return keyword_scores(text, descriptions)
        if len(scored) != len(descriptions):
            return keyword_scores(text, descriptions)
        return scored

    def _fit(self, selections: Sequence[Selection]) -> tuple[list[Selection], list[str]]:
        """Keep selections in order until the character budget runs out.

        In order, so what gets dropped is what was chosen with the least confidence. A pinned
        skill is never dropped for a retrieved one.
        """
        kept: list[Selection] = []
        dropped: list[str] = []
        spent = 0
        for selection in selections:
            cost = len(selection.skill.body)
            if kept and spent + cost > self.budget_chars:
                dropped.append(selection.skill.id)
                continue
            spent += cost
            kept.append(selection)
        return kept, dropped

"""hera_skillsets — ``SKILL.md`` packages, and the router that picks them server-side.

A skill is a directory under ``$HERA_HOME/skills`` holding a ``SKILL.md``: YAML frontmatter
with a name and a description, then Markdown. The format is Claude Code's, unchanged, so the
same folder works in both (ADR 5).

The router chooses which skills a turn gets — **pinned**, then ``/slash``, then **retrieved** —
and it never asks the model, because the target model does not reliably notice that a skill
applies. Every selection carries why it was chosen, which is what the activity gutter shows and
the only feedback loop that reveals retrieval picking the wrong thing.
"""

from __future__ import annotations

from hera_skillsets.errors import SkillsError, UnknownSkill
from hera_skillsets.library import Catalogue, SkillLibrary, SkillLibraryPort
from hera_skillsets.loader import load_skill
from hera_skillsets.models import ID_PATTERN, SKILL_FILENAME, BrokenSkill, Skill, SkillUsage
from hera_skillsets.render import render
from hera_skillsets.repository import SkillUsageRepository
from hera_skillsets.retrieval import Embedder, keyword_scores, tokenise
from hera_skillsets.router import (
    DEFAULT_BUDGET_CHARS,
    DEFAULT_FLOOR,
    DEFAULT_LIMIT,
    Reason,
    Routing,
    Selection,
    SkillRouter,
)

__all__ = [
    "DEFAULT_BUDGET_CHARS",
    "DEFAULT_FLOOR",
    "DEFAULT_LIMIT",
    "ID_PATTERN",
    "SKILL_FILENAME",
    "BrokenSkill",
    "Catalogue",
    "Embedder",
    "Reason",
    "Routing",
    "Selection",
    "Skill",
    "SkillLibrary",
    "SkillLibraryPort",
    "SkillRouter",
    "SkillUsage",
    "SkillUsageRepository",
    "SkillsError",
    "UnknownSkill",
    "keyword_scores",
    "load_skill",
    "render",
    "tokenise",
]

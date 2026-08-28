"""hera_profiles — the mind, and the profiles that select from it.

Answers *who she is*. Her character, role, tone, conduct and the rest live as Markdown files
in a git repository at ``$HERA_HOME/mind``, one file per **region**; a **profile** is a row
that picks which of them apply, overrides individual ones, and sets a handful of behaviour
traits. :class:`PromptBuilder` turns the two into a :class:`hera_prompts.Prompt` with named
slots left open for everything this package is not allowed to know about — tools, skills,
memories and the current project.

What it never does: render, stream, or decide what goes into a slot.
"""

from __future__ import annotations

from hera_profiles.builder import (
    LAYOUT,
    LAYOUT_REGIONS,
    LAYOUT_SLOTS,
    SLOT_EMOTIONS,
    SLOT_MEMORIES,
    SLOT_NOW,
    SLOT_PROJECT,
    SLOT_SKILLS,
    SLOT_TOOLS,
    SLOTS,
    Node,
    PromptBuilder,
)
from hera_profiles.errors import (
    MindError,
    NoSuchVersion,
    ProfilesError,
    RegionLocked,
    UnknownRegion,
)
from hera_profiles.mind import ORIGIN_TRAILER, MindRepository, RegionVersion
from hera_profiles.models import DEFAULT_SLUG, Profile
from hera_profiles.regions import (
    EVOLVABLE_REGIONS,
    MIND_REGIONS,
    REGIONS_BY_ID,
    MindRegion,
    Tier,
    filename,
    region,
)
from hera_profiles.repository import ProfileRepository, slugify
from hera_profiles.traits import BEHAVIOUR_TRAITS, DEPTH, EMOJI, FORMALITY, LANGUAGE

__all__ = [
    "BEHAVIOUR_TRAITS",
    "DEFAULT_SLUG",
    "DEPTH",
    "EMOJI",
    "EVOLVABLE_REGIONS",
    "FORMALITY",
    "LANGUAGE",
    "LAYOUT",
    "LAYOUT_REGIONS",
    "LAYOUT_SLOTS",
    "MIND_REGIONS",
    "ORIGIN_TRAILER",
    "REGIONS_BY_ID",
    "SLOTS",
    "SLOT_EMOTIONS",
    "SLOT_MEMORIES",
    "SLOT_NOW",
    "SLOT_PROJECT",
    "SLOT_SKILLS",
    "SLOT_TOOLS",
    "MindError",
    "MindRegion",
    "MindRepository",
    "NoSuchVersion",
    "Node",
    "Profile",
    "ProfileRepository",
    "ProfilesError",
    "PromptBuilder",
    "RegionLocked",
    "RegionVersion",
    "Tier",
    "UnknownRegion",
    "filename",
    "region",
    "slugify",
]

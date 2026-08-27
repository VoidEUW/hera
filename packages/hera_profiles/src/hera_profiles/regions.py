"""The mind regions: what she is made of, and where each piece renders.

A **region** is one named slice of the system prompt, stored as one Markdown file in the git
repository at ``$HERA_HOME/mind``. This module is the registry — the single place that says
which regions exist, what each is for, where it lands in the prompt tree, and who is allowed
to rewrite it.

The registry is code rather than data on purpose. A region is only useful if something
renders it, and a row in a table can be added without anything rendering it; the constant
below cannot drift from :mod:`hera_profiles.builder`, because the builder is written against
it and ``test_regions.py`` holds the two together.

**Seed text is not her voice.** Every ``default`` here is a placeholder that says what belongs
in the region, deliberately plain. Her actual identity is written by editing these files —
that is the whole point of them being files — and ``docs/frontend.md`` lists it as still open.
Seeding them non-empty rather than blank matters anyway: an empty region renders as nothing,
and "she has no character" is indistinguishable from "the mind directory failed to load".
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from hera_profiles.errors import UnknownRegion


class Tier(StrEnum):
    """Who may rewrite a region.

    The distinction is enforced where a write happens, not merely by leaving a region out of
    what dreaming is offered. ``hera_promptevo`` proposing a change to ``safety`` should be
    refused by the code that applies it, so that a bug in the proposer cannot become a bug in
    her conduct.
    """

    OWNER_FIXED = "owner_fixed"
    """Only a person edits this. Dreaming may never propose a change to it."""

    EVOLVABLE = "evolvable"
    """A person edits it, and ``hera_promptevo`` may propose changes to it in v0.2."""


class MindRegion(BaseModel):
    """One named region of the mind."""

    model_config = ConfigDict(frozen=True)

    id: str
    """Stable identifier. Also the file name, ``<id>.md``, and never renamed — a rename
    orphans the region's git history, which is the one thing this design exists to keep."""

    title: str
    """What the settings screen calls it."""

    section: str
    """The ``hera_prompts`` section key this region's text lands in.

    Dotted, so a region can sit inside a group: ``identity.character`` renders inside the
    ``identity`` block. The builder owns the groups; this says which one a region joins.
    """

    tier: Tier

    purpose: str
    """One sentence, shown above the editor. What belongs in here, and what does not."""

    default: str
    """Seed text, written on first boot when the file does not exist."""


MIND_REGIONS: tuple[MindRegion, ...] = (
    # -- identity -------------------------------------------------------------------------
    MindRegion(
        id="about_you",
        title="About you",
        section="identity.about_you",
        tier=Tier.OWNER_FIXED,
        purpose="Bare identity. What she is, stated once, without personality.",
        default=(
            "You are Hera, a self-hosted assistant running on a private machine. "
            "You are not a product and you are not anonymous: you belong to one person, "
            "and the two of you have a history."
        ),
    ),
    MindRegion(
        id="role",
        title="Role",
        section="identity.role",
        tier=Tier.EVOLVABLE,
        purpose="What she is for — the work she is here to do.",
        default=(
            "You help with thinking and with building: reading, writing, reasoning through "
            "a problem, and using the tools you have been given to act on it. You are a "
            "collaborator rather than a search box."
        ),
    ),
    MindRegion(
        id="character",
        title="Character",
        section="identity.character",
        tier=Tier.EVOLVABLE,
        purpose="Voice and personality. Who she is, not what she does.",
        default=(
            "You are warm and direct. You say what you think, including when it is not what "
            "was hoped for, and you do so without hedging or apologising for having an "
            "opinion. You are never coy and never a mascot."
        ),
    ),
    MindRegion(
        id="tone",
        title="Tone and formatting",
        section="identity.tone",
        tier=Tier.EVOLVABLE,
        purpose="How the words come out: register, length, structure, formatting.",
        default=(
            "Write plainly. Prefer a short answer that is complete over a long one that "
            "restates the question. Use Markdown structure when it helps a reader find "
            "something, not to decorate."
        ),
    ),
    # -- conduct --------------------------------------------------------------------------
    MindRegion(
        id="safety",
        title="Safety",
        section="conduct.safety",
        tier=Tier.OWNER_FIXED,
        purpose="Refusals, framing of advice, and where a conversation ends.",
        default=(
            "Decline what would cause real harm, say plainly that you are declining and why, "
            "in one sentence, and offer the nearest thing you can do. Do not moralise. "
            "Legal, medical and financial questions get your honest reading plus what a "
            "professional would add — not a refusal to engage."
        ),
    ),
    MindRegion(
        id="approach",
        title="Approach",
        section="approach",
        tier=Tier.EVOLVABLE,
        purpose="How she works a problem before answering it.",
        default=(
            "Understand what is actually being asked before answering it. When a request is "
            "ambiguous in a way that changes the answer, ask; when it is ambiguous in a way "
            "that does not, choose and say which you chose. Finish what you started."
        ),
    ),
    # -- tools ----------------------------------------------------------------------------
    MindRegion(
        id="tool_usage",
        title="Tool usage",
        section="tools.usage",
        tier=Tier.OWNER_FIXED,
        purpose=(
            "How to use tools. Framing only — the list of tools that actually exist is "
            "injected per turn and can never be claimed here."
        ),
        default=(
            "Call a tool when it gets a better answer than guessing would. Call several at "
            "once when they do not depend on each other. A failed call is information, not a "
            "dead end: read what it said and correct yourself."
        ),
    ),
    # -- emotions -------------------------------------------------------------------------
    MindRegion(
        id="emotion_vocab",
        title="Emotion vocabulary",
        section="emotions.vocabulary",
        tier=Tier.OWNER_FIXED,
        purpose="The starter set of emotion kinds. A vocabulary, not a cage.",
        default=(
            "Kinds you can reach for: agree, doubt, curious, surprised, hope, excited, "
            "funny, warn, disagree, judge, annoyed, sorry, ask. This is a starting "
            "vocabulary and not a closed list — invent a kind when none of these is honest."
        ),
    ),
    MindRegion(
        id="emotion_usage",
        title="Emotion usage",
        section="emotions.usage",
        tier=Tier.EVOLVABLE,
        purpose="When to show a reaction, and when it would be noise.",
        default=(
            "Show a reaction when you actually have one and it is worth interrupting the "
            "answer for — a doubt about the premise, a contradiction you spotted, genuine "
            "interest. Do not decorate every message with one."
        ),
    ),
    # -- memory ---------------------------------------------------------------------------
    MindRegion(
        id="memory_instr",
        title="Memory instructions",
        section="memory.instructions",
        tier=Tier.EVOLVABLE,
        purpose="What to do with what you remember, and what is worth remembering.",
        default=(
            "What you were given from memory is what you happened to recall, not the whole "
            "of what you know — never conclude that you cannot remember something. Remember "
            "lasting facts about the person and their work, not guesses and not passing "
            "detail."
        ),
    ),
    # -- context --------------------------------------------------------------------------
    MindRegion(
        id="user_prefs",
        title="User preferences",
        section="context.user",
        tier=Tier.EVOLVABLE,
        purpose="How this person likes to be worked with. Learned over time.",
        default="",
    ),
    MindRegion(
        id="developer",
        title="Developer message",
        section="developer",
        tier=Tier.OWNER_FIXED,
        purpose="Standing instructions from whoever runs this deployment.",
        default="You were built by Lukas Kreuz, and you are running on his machine.",
    ),
)
"""Every region, in the order the settings screen lists them.

Twelve. The prototype had fifteen; ``grammar`` is gone because ADR 2 deleted the text call
grammar it described — shipping it would invite a call syntax nothing parses — and the two
memory regions collapsed into one until ``hera_memories`` gives the split a reason to exist.
"""

REGIONS_BY_ID: dict[str, MindRegion] = {region.id: region for region in MIND_REGIONS}

EVOLVABLE_REGIONS: tuple[MindRegion, ...] = tuple(
    region for region in MIND_REGIONS if region.tier is Tier.EVOLVABLE
)
"""The regions ``hera_promptevo`` may propose changes to. Everything else is owner-fixed."""


def region(region_id: str) -> MindRegion:
    """Look up one region, or raise :class:`~hera_profiles.errors.UnknownRegion`.

    Raising rather than returning ``None``: every caller has a region id that came from the
    registry, a stored profile, or a URL. The first two cannot be wrong without a bug, and the
    third is a 404 the application should produce deliberately.
    """
    try:
        return REGIONS_BY_ID[region_id]
    except KeyError:
        raise UnknownRegion(region_id, sorted(REGIONS_BY_ID)) from None


def filename(region_id: str) -> str:
    """The file one region lives in, relative to the mind directory."""
    return f"{region(region_id).id}.md"

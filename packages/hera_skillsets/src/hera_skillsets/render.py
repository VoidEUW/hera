"""Selected skills, as the string that goes into the ``skills`` prompt slot.

Markdown, not XML. A skill body is somebody else's Markdown and routinely contains code, and
``hera_prompts``' XML renderer escapes ``<``, ``>`` and ``&`` in section text — so anything
tag-shaped emitted here would arrive at the model as ``&lt;tag&gt;``. Markdown headings
survive that untouched, which makes them the honest choice rather than merely the plain one.

The catalogue line at the end is ADR 5's other half: selection is code, and the model is still
told what else exists so that one which *does* reach for a skill mid-task can call
``hera__skill``. Nothing depends on that happening.
"""

from __future__ import annotations

from collections.abc import Sequence

from hera_skillsets.models import Skill
from hera_skillsets.router import Reason, Routing, Selection

RULE = "\n\n---\n\n"

_WHY = {
    Reason.PINNED: "always active for this profile",
    Reason.SLASH: "you asked for it by name",
    Reason.RETRIEVED: "matched what this turn is about",
}


def render(routing: Routing, *, catalogue: Sequence[Skill] = ()) -> str:
    """The whole ``skills`` slot: the selected skills in full, then what else exists.

    Returns ``""`` when there is nothing to say, which leaves the slot unbound and the section
    out of the prompt entirely — rather than telling the model it has no skills, which is a
    different and less useful sentence.
    """
    blocks = [_block(selection) for selection in routing.selections]
    remainder = _catalogue(catalogue, exclude=set(routing.ids()))
    if remainder:
        blocks.append(remainder)
    return RULE.join(blocks)


def _block(selection: Selection) -> str:
    skill = selection.skill
    lines = [f"# Skill: {skill.id}", f"_{_WHY[selection.reason]}_"]
    if skill.description:
        lines.append("")
        lines.append(skill.description)
    lines.append("")
    lines.append(skill.body)
    if skill.resources:
        lines.append("")
        lines.append(
            f"This skill has further files beside it in `{skill.path}`: "
            f"{', '.join(skill.resources)}. Read one if this skill tells you to."
        )
    return "\n".join(lines)


def _catalogue(skills: Sequence[Skill], *, exclude: set[str]) -> str:
    """One line per skill that was not selected.

    Names and descriptions only. Loading one is a `hera__skill` call, which is the door ADR 5
    leaves open rather than the mechanism it relies on.
    """
    rest = [skill for skill in skills if skill.id not in exclude and skill.usable]
    if not rest:
        return ""
    lines = [
        "# Other skills installed",
        "Not selected for this turn. Call `hera__skill(name)` if one turns out to apply.",
        "",
    ]
    lines.extend(f"- `{skill.id}` — {skill.description or 'no description'}" for skill in rest)
    return "\n".join(lines)

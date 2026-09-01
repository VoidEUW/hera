"""Turning the mind into a prompt.

This is the seam ``docs/status.md`` describes as *mind regions → Prompt, slots bound*. The
builder produces a :class:`hera_prompts.Prompt` and stops. It does not render it, does not
know what a chat is, and — importantly — does not know what a tool, a skill, a memory or a
project is either: those enter as **slots**, named holes that the layer owning the turn fills
with pre-rendered strings.

That is the whole reason ``hera_prompts`` refuses to import anything. A section like
``tools.available`` is a promise that something will supply text; who supplies it, and whether
the deployment has any tools at all, is settled above. An unbound, non-required slot renders as
nothing rather than as an empty tag, so a Hera with no MCP servers configured does not tell the
model about an empty tool list.

**The layout is code, not configuration.** Where a region lands, what it sits inside, and what
gets dropped first under budget pressure are decisions with consequences a person has to be
able to read. :data:`LAYOUT` below is that reading.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from hera_profiles.mind import MindRepository
from hera_profiles.models import Profile
from hera_profiles.traits import BEHAVIOUR_TRAITS
from hera_prompts import (
    Prompt,
    RejectedChange,
    RendererConfig,
    Role,
    Section,
    TraitPatch,
    TraitRegistry,
)

SLOT_TOOLS = "tools"
"""The tool catalogue, rendered by whoever owns ``hera_tools``."""

SLOT_SKILLS = "skills"
"""The skills the router selected for this turn (ADR 5), already rendered."""

SLOT_MEMORIES = "memories"
"""What was recalled for this turn. Unbound until ``hera_memories`` lands in v0.2."""

SLOT_PROJECT = "project"
"""The instructions of the project this chat lives in, if it lives in one."""

SLOT_NOW = "now"
"""What the date and time are, rendered by the application.

A slot rather than a mind region: it is a *fact about this moment*, not a behaviour somebody
should be able to edit. A region saying "it is Tuesday" would be wrong by Wednesday.
"""

SLOTS: frozenset[str] = frozenset({SLOT_TOOLS, SLOT_SKILLS, SLOT_MEMORIES, SLOT_PROJECT, SLOT_NOW})
"""Every slot the skeleton offers.

Named constants rather than string literals at the call site: a typo in a binding key is
otherwise invisible — the binding lands in ``unused_bindings``, the section lands in
``unbound_slots``, and the prompt is quietly missing a third of its context.
"""


@dataclass(frozen=True)
class Node:
    """One section of the skeleton, before it has any text.

    Exactly one of ``region``, ``slot`` and ``children`` is meaningful — a section that both
    holds content and has children is rejected by ``hera_prompts`` anyway, and the redundancy
    here is cheaper than discovering that at render time.
    """

    key: str
    title: str
    priority: int
    required: bool = False
    role: Role = Role.SYSTEM
    region: str | None = None
    slot: str | None = None
    children: tuple[Node, ...] = ()


LAYOUT: tuple[Node, ...] = (
    Node(
        key="developer",
        title="Developer message",
        priority=1,
        required=True,
        role=Role.DEVELOPER,
        region="developer",
    ),
    Node(
        key="conduct",
        title="Conduct",
        priority=5,
        required=True,
        children=(
            Node(key="conduct.safety", title="Safety", priority=5, required=True, region="safety"),
        ),
    ),
    Node(
        key="identity",
        title="Identity",
        priority=10,
        required=True,
        children=(
            Node(
                key="identity.about_you",
                title="About you",
                priority=10,
                required=True,
                region="about_you",
            ),
            Node(key="identity.role", title="Role", priority=20, region="role"),
            Node(key="identity.character", title="Character", priority=20, region="character"),
            Node(key="identity.tone", title="Tone", priority=30, region="tone"),
            Node(key="identity.language", title="Language", priority=31, region="language"),
        ),
    ),
    Node(
        key="approach",
        title="Approach",
        priority=40,
        children=(
            Node(key="approach.method", title="How to work", priority=40, region="approach"),
            Node(
                key="approach.uncertainty",
                title="When you are not sure",
                priority=41,
                region="uncertainty",
            ),
            Node(
                key="approach.correction",
                title="When you are wrong",
                priority=42,
                region="correction",
            ),
        ),
    ),
    # There was an `emotions` group here, holding a vocabulary slot and a region about when to
    # use one. ADR 17 removed both: a stance she means is a sentence she writes, and the tool
    # that made it a separate thing is gone. Nothing took the priority band -- the numbers are
    # ordering, not addresses, and closing the gap would only make a diff look bigger.
    Node(
        key="tools",
        title="Tools",
        priority=50,
        children=(
            Node(key="tools.usage", title="How to use them", priority=51, region="tool_usage"),
            Node(key="tools.available", title="Available", priority=50, slot=SLOT_TOOLS),
        ),
    ),
    Node(
        key="memory",
        title="Memory",
        priority=55,
        children=(
            Node(
                key="memory.instructions", title="How to use it", priority=56, region="memory_instr"
            ),
            Node(key="memory.recalled", title="Recalled", priority=55, slot=SLOT_MEMORIES),
        ),
    ),
    Node(key="skills", title="Skills", priority=60, slot=SLOT_SKILLS),
    Node(
        key="context",
        title="Context",
        priority=70,
        children=(
            # First in the group and low-priority on purpose: it is one line, and a model that
            # does not know the date answers "what is current" from its training data — a whole
            # class of confidently stale answers for thirty tokens.
            Node(key="context.now", title="Right now", priority=68, slot=SLOT_NOW),
            Node(key="context.project", title="This project", priority=70, slot=SLOT_PROJECT),
            Node(key="context.user", title="About this person", priority=71, region="user_prefs"),
        ),
    ),
)
"""The prompt tree.

Read the ``priority`` column as *what goes first when the context window runs out*: lowest
goes first, and ``required`` is never dropped at all. So identity, conduct and the developer
message survive any budget, and the things she can look up again — the tool catalogue,
recalled memories, project context — are what gives way. A skill the router chose sits below
those, because dropping it silently would defeat the point of choosing it in code.

``skills`` is a top-level leaf rather than a group with one child: a group wrapping a single
section renders as a tag inside an identical tag and says nothing. ``approach`` was one too
until ``uncertainty`` and ``correction`` joined it, which is what earned it the group — three
sections about how she works a problem, kept together so the model reads them as one stance
rather than as three unrelated paragraphs.
"""


def _walk(nodes: Sequence[Node]) -> list[Node]:
    """Every node in the layout, depth first."""
    found: list[Node] = []
    for node in nodes:
        found.append(node)
        found.extend(_walk(node.children))
    return found


class PromptBuilder:
    """Mind regions plus a profile, compiled into a :class:`hera_prompts.Prompt`.

    Cheap to call: twelve small file reads and a tree walk. Nothing is cached, because the
    settings screen edits a region and expects the very next turn to use it — and a cache
    invalidated by a git commit is a cache invalidated by something outside this process.
    """

    def __init__(
        self,
        mind: MindRepository,
        *,
        registry: TraitRegistry = BEHAVIOUR_TRAITS,
        layout: Sequence[Node] = LAYOUT,
    ) -> None:
        self.mind = mind
        self.registry = registry
        self.layout = tuple(layout)

    def build(self, profile: Profile | None = None) -> Prompt:
        """The prompt for one profile, or for the bare mind when given none.

        Regions this profile disables, and regions whose text is empty, are left out
        entirely rather than rendered as empty tags — an empty element in the prompt is a
        sentence to the model saying "this exists and has nothing in it".
        """
        texts = self.texts(profile)
        sections = [
            section
            for section in (_section(node, texts) for node in self.layout)
            if section is not None
        ]
        prompt = Prompt(
            sections=sections,
            traits=self.registry.defaults(),
            renderer=self._renderer(profile),
        )
        if profile is None or not profile.traits:
            return prompt
        return prompt.apply(_patch(profile), registry=self.registry).prompt

    def texts(self, profile: Profile | None = None) -> dict[str, str]:
        """The text of every region under this profile, keyed by region id.

        A profile's override replaces the file's text; a disabled region comes back empty,
        which is what makes it disappear from :meth:`build`. Exposed on its own so the
        settings screen can show exactly what a profile will say without rendering a prompt.
        """
        current = self.mind.read_all()
        if profile is None:
            return current
        disabled = set(profile.disabled_regions)
        return {
            region_id: "" if region_id in disabled else profile.overrides.get(region_id, text)
            for region_id, text in current.items()
        }

    def rejected_traits(self, profile: Profile) -> list[RejectedChange]:
        """Traits this profile carries that the registry would not admit today.

        A profile is a stored row and outlives the specs it was written against: narrow a
        trait's ``choices`` and older profiles keep a value no patch would accept. Rendering
        drops those silently, which is correct at run time and useless at a settings screen —
        hence this.
        """
        if not profile.traits:
            return []
        return (
            Prompt(traits=self.registry.defaults())
            .apply(_patch(profile), registry=self.registry)
            .rejected
        )

    def _renderer(self, profile: Profile | None) -> RendererConfig:
        if profile is None:
            return RendererConfig(format="xml")
        return RendererConfig.model_validate({"format": profile.renderer_format})


def _patch(profile: Profile) -> TraitPatch:
    return TraitPatch(changes=dict(profile.traits))


def _section(node: Node, texts: Mapping[str, str]) -> Section | None:
    """One node as a section, or ``None`` when it would carry nothing.

    A slot node always survives: whether a binding exists is a render-time question, and
    ``hera_prompts`` already drops an unbound, non-required slot. A region node survives only
    if its region has text.
    """
    if node.slot is not None:
        return _build(node, slot=node.slot)
    if node.region is not None:
        text = texts.get(node.region, "").strip()
        return _build(node, content=text) if text else None
    children = [
        child for child in (_section(child, texts) for child in node.children) if child is not None
    ]
    return _build(node, children=children) if children else None


def _build(
    node: Node,
    *,
    content: str | None = None,
    slot: str | None = None,
    children: list[Section] | None = None,
) -> Section:
    return Section(
        key=node.key,
        title=node.title,
        content=content,
        slot=slot,
        children=children or [],
        role=node.role,
        priority=node.priority,
        required=node.required,
        # A slot holds somebody else's prose -- a skill body, a project's instructions, a tool
        # catalogue -- and those routinely contain code. Escaping would hand the model
        # `if count &lt; limit` and then expect it to learn from the sample. A region is text
        # from the mind repository and is escaped like everything else this package authors.
        escape=slot is None,
    )


LAYOUT_REGIONS: frozenset[str] = frozenset(
    node.region for node in _walk(LAYOUT) if node.region is not None
)
"""Region ids the layout actually renders.

``test_builder.py`` holds this against :data:`hera_profiles.regions.MIND_REGIONS`: a region in
the registry that no node renders is a region nobody will ever read, and a node naming a region
that does not exist is a section that is always empty. Both are silent, and both are bugs.
"""

LAYOUT_SLOTS: frozenset[str] = frozenset(
    node.slot for node in _walk(LAYOUT) if node.slot is not None
)

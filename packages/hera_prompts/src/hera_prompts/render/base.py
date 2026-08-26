"""The format-independent half of rendering.

Pruning, slot resolution, trait routing and message assembly happen here; the three
renderers only turn the resulting blocks into text.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Protocol

from hera_prompts.errors import MissingBinding
from hera_prompts.models import Message, RendererConfig, Role, Section
from hera_prompts.prompt import Prompt
from hera_prompts.traits import TraitRegistry, TraitSpec, TraitValue, format_value

GENERAL_KEY = "general"
"""Key of the block that collects traits without a section of their own."""


@dataclass(frozen=True)
class TraitLine:
    """One trait on its way into a block."""

    key: str
    group: str
    name: str
    value: TraitValue
    spec: TraitSpec | None

    def raw(self, separator: str) -> str:
        """The bare grammar, ``GROUP name = value``."""
        return f"{self.group}{separator}{self.name} = {format_value(self.value)}"

    def pair(self) -> str:
        """The pair without its group, ``name = value``."""
        return f"{self.name} = {format_value(self.value)}"

    def sentence(self, separator: str, container: str) -> str:
        """The prose form from the spec's template, falling back to the pair.

        ``container`` is the key of the block the trait renders in. Formats that carry
        the address structurally — a tag, a heading — get the pair without its group,
        because repeating ``BEHAVIOR`` inside ``<behavior>`` is noise. A trait whose
        prefix points somewhere else, and therefore ended up in the general block, keeps
        its full address: there the group is the only thing that still says where it
        belongs.
        """
        if self.spec is not None:
            text = self.spec.rendered_sentence(self.value)
            if text is not None:
                return text
        if self.group == container.upper():
            return self.pair()
        return self.raw(separator)


@dataclass(frozen=True)
class Block:
    """A section as it will be rendered: text resolved, traits attached.

    ``section`` is ``None`` for the general block, which has no section behind it.
    """

    key: str
    title: str
    text: str | None
    traits: tuple[TraitLine, ...]
    children: tuple[Block, ...]
    section: Section | None = None

    @property
    def leaf_key(self) -> str:
        return self.key.rsplit(".", 1)[-1]

    def walk(self) -> Iterator[Block]:
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass(frozen=True)
class Plan:
    """The blocks of one rendering, grouped by the role of their root section."""

    system: tuple[Block, ...]
    developer: tuple[Block, ...]
    user: tuple[Block, ...]

    def walk(self) -> Iterator[Block]:
        for block in (*self.system, *self.developer, *self.user):
            yield from block.walk()


class Renderer(Protocol):
    """Turns one top-level block into text."""

    block_separator: str

    def block(self, block: Block, config: RendererConfig, depth: int = 0) -> str: ...


@dataclass(frozen=True)
class _Node:
    section: Section
    text: str | None
    children: tuple[_Node, ...]

    def walk(self) -> Iterator[_Node]:
        yield self
        for child in self.children:
            yield from child.walk()


def build_plan(
    prompt: Prompt,
    bindings: Mapping[str, str],
    registry: TraitRegistry,
    dropped: frozenset[str],
) -> Plan:
    """Resolve a prompt into blocks: disabled and dropped sections gone, slots filled,
    traits routed."""
    nodes = [
        node
        for node in (_resolve(section, bindings, dropped) for section in prompt.sections)
        if node is not None
    ]
    present = {inner.section.key for node in nodes for inner in node.walk()}
    routed, general = _route_traits(prompt, registry, present)

    blocks = [block for block in (_block(node, routed) for node in nodes) if block is not None]
    system: list[Block] = []
    if general:
        system.append(
            Block(
                key=GENERAL_KEY,
                title=GENERAL_KEY,
                text=None,
                traits=tuple(general),
                children=(),
            )
        )
    system.extend(block for block in blocks if _role(block) is Role.SYSTEM)
    return Plan(
        system=tuple(system),
        developer=tuple(block for block in blocks if _role(block) is Role.DEVELOPER),
        user=tuple(block for block in blocks if _role(block) is Role.USER),
    )


def used_slots(prompt: Prompt) -> set[str]:
    """Slot names an enabled section refers to — the counterpart to unused bindings.

    Computed before any budget pressure: a section dropped for budget reasons appears in
    ``dropped_keys``, and its binding should not be reported as unused on top of that.
    """
    return {
        node.slot for root in prompt.sections for node in _enabled(root) if node.slot is not None
    }


def unbound_slots(prompt: Prompt, bindings: Mapping[str, str]) -> list[str]:
    """Slots of enabled sections that no binding filled, so the section was left out.

    Kept apart from ``dropped_keys`` and ``unused_bindings``: three different causes for
    missing content, and lumping them together would make all three useless when
    something has to be traced back.
    """
    return sorted(
        {
            node.slot
            for root in prompt.sections
            for node in _enabled(root)
            if node.slot is not None and node.slot not in bindings
        }
    )


def to_messages(plan: Plan, config: RendererConfig, renderer: Renderer) -> list[Message]:
    """Assemble the messages. Empty messages are left out entirely."""

    def joined(blocks: tuple[Block, ...]) -> str:
        return renderer.block_separator.join(renderer.block(block, config) for block in blocks)

    messages: list[Message] = []
    if config.developer_role == "fold_into_system":
        folded = plan.system + plan.developer
        if folded:
            messages.append(Message(role=Role.SYSTEM, content=joined(folded)))
    else:
        if plan.system:
            messages.append(Message(role=Role.SYSTEM, content=joined(plan.system)))
        if plan.developer:
            messages.append(Message(role=Role.DEVELOPER, content=joined(plan.developer)))
    if plan.user:
        messages.append(Message(role=Role.USER, content=joined(plan.user)))
    return messages


def next_drop_candidate(plan: Plan) -> str | None:
    """The section to drop next under budget pressure: lowest priority first, ties
    resolved by key. A required section — or one with a required descendant — is safe."""
    candidates = [
        block.section
        for block in plan.walk()
        if block.section is not None
        and not any(inner.section is not None and inner.section.required for inner in block.walk())
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda section: (section.priority, section.key)).key


def _resolve(
    section: Section, bindings: Mapping[str, str], dropped: frozenset[str]
) -> _Node | None:
    if not section.enabled or section.key in dropped:
        return None
    text = section.content
    if section.slot is not None:
        if section.slot in bindings:
            text = bindings[section.slot]
        elif section.required:
            raise MissingBinding(
                f"section {section.key!r} requires a binding for slot {section.slot!r}"
            )
        else:
            return None
    children = tuple(
        child
        for child in (_resolve(child, bindings, dropped) for child in section.children)
        if child is not None
    )
    return _Node(section=section, text=text, children=children)


def _enabled(section: Section) -> Iterator[Section]:
    if not section.enabled:
        return
    yield section
    for child in section.children:
        yield from _enabled(child)


def _ordered_traits(prompt: Prompt, registry: TraitRegistry) -> list[tuple[str, TraitValue]]:
    """Declared traits in the order the registry declares them, the rest by key.

    The declared order is a curated one — it is what the reference example pins down —
    and the prompt itself keeps its traits sorted, so the result never depends on how a
    prompt was built.
    """
    declared = [spec.key for spec in registry.specs]
    known = [(key, prompt.traits[key]) for key in declared if key in prompt.traits]
    rest = sorted(
        ((key, value) for key, value in prompt.traits.items() if key not in set(declared)),
        key=lambda item: item[0],
    )
    return known + rest


def _route_traits(
    prompt: Prompt, registry: TraitRegistry, present: set[str]
) -> tuple[dict[str, list[TraitLine]], list[TraitLine]]:
    routed: dict[str, list[TraitLine]] = {}
    general: list[TraitLine] = []
    for key, value in _ordered_traits(prompt, registry):
        prefix, _, name = key.rpartition(".")
        line = TraitLine(
            key=key,
            group=prefix.upper() if prefix else GENERAL_KEY.upper(),
            name=name,
            value=value,
            spec=registry.get(key),
        )
        if prefix and prefix in present:
            routed.setdefault(prefix, []).append(line)
        else:
            general.append(line)
    return routed, general


def _block(node: _Node, routed: dict[str, list[TraitLine]]) -> Block | None:
    children = tuple(
        block for block in (_block(child, routed) for child in node.children) if block is not None
    )
    traits = tuple(routed.get(node.section.key, ()))
    if node.text is None and not traits and not children:
        return None
    return Block(
        key=node.section.key,
        title=node.section.title or node.section.key,
        text=node.text,
        traits=traits,
        children=children,
        section=node.section,
    )


def _role(block: Block) -> Role:
    return block.section.role if block.section is not None else Role.SYSTEM

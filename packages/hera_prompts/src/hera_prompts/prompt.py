"""The prompt object: navigation, transformations, identity and the entry point to rendering."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hera_prompts.canonical import sha256_hex
from hera_prompts.errors import SectionError, TraitError
from hera_prompts.models import KEY_PATTERN, RendererConfig, Section
from hera_prompts.traits import (
    PatchResult,
    RejectedChange,
    TraitPatch,
    TraitRegistry,
    TraitValue,
)

if TYPE_CHECKING:
    from hera_prompts.render.budget import TokenBudget
    from hera_prompts.snapshot import RenderResult

ROOT = ""
"""Passed as ``parent`` to address the top level of the tree."""


class Prompt(BaseModel):
    """An immutable, serialisable prompt.

    Every transformation returns a new object. A prompt survives
    ``model_dump_json()`` and back without loss — otherwise the layer above could not
    store it.
    """

    model_config = ConfigDict(frozen=True)

    sections: list[Section] = Field(default_factory=list)
    traits: dict[str, TraitValue] = Field(default_factory=dict)
    locked_traits: frozenset[str] = frozenset()
    renderer: RendererConfig = RendererConfig()

    @field_validator("traits")
    @classmethod
    def _sorted_traits(cls, traits: dict[str, TraitValue]) -> dict[str, TraitValue]:
        """Store traits sorted by key, so insertion order can never leak into a
        fingerprint or a rendering."""
        for key in traits:
            if not KEY_PATTERN.match(key):
                raise TraitError(f"invalid trait key: {key!r}")
        return dict(sorted(traits.items()))

    @model_validator(mode="after")
    def _validate_prompt(self) -> Prompt:
        seen: set[str] = set()
        for root in self.sections:
            for node in root.walk():
                if node.key in seen:
                    raise SectionError(f"duplicate section key: {node.key!r}")
                seen.add(node.key)
        return self

    # -- navigation ----------------------------------------------------------

    def paths(self) -> list[str]:
        """All section keys in document order."""
        return [node.key for root in self.sections for node in root.walk()]

    def get(self, key: str) -> Section | None:
        """The section addressed by ``key``, or ``None``."""
        for root in self.sections:
            for node in root.walk():
                if node.key == key:
                    return node
        return None

    def is_locked(self, key: str) -> bool:
        """Whether the section addressed by ``key`` is locked. Unknown keys are not."""
        section = self.get(key)
        return section is not None and section.locked

    def _require(self, key: str) -> Section:
        section = self.get(key)
        if section is None:
            raise SectionError(f"unknown section: {key!r}")
        return section

    # -- transformations, each returning a new object ------------------------

    def replace(self, key: str, *, content: str | None = None, title: str | None = None) -> Prompt:
        """Set content and/or title of a section.

        A locked section leaves the prompt untouched and returns it unchanged; there is
        no return channel for that rejection here, so ask :meth:`is_locked` beforehand
        if you need to know. An unknown key raises :class:`SectionError` — a stale
        address is a caller error, not a policy decision, and must not pass silently.
        """
        if self._require(key).locked:
            return self
        updates: dict[str, Any] = {}
        if content is not None:
            updates["content"] = content
        if title is not None:
            updates["title"] = title
        if not updates:
            return self
        return self._map_section(key, lambda section: _rebuild(section, **updates))

    def insert(self, parent: str, section: Section, *, after: str | None = None) -> Prompt:
        """Insert ``section`` below ``parent``, optionally after a given sibling.

        Pass :data:`ROOT` as ``parent`` to insert at the top level. A locked parent
        leaves the prompt unchanged; an unknown parent or a key that does not sit below
        it raises :class:`SectionError`.
        """
        if parent != ROOT:
            if self.get(parent) is None:
                raise SectionError(f"unknown parent section: {parent!r}")
            if not section.key.startswith(f"{parent}."):
                raise SectionError(
                    f"section key {section.key!r} is not prefixed with {parent!r} plus a dot"
                )
            if self.is_locked(parent):
                return self
        elif "." in section.key:
            raise SectionError(f"top level section key must not contain a dot: {section.key!r}")

        def place(children: list[Section]) -> list[Section]:
            if after is None:
                return [*children, section]
            for index, child in enumerate(children):
                if child.key == after:
                    return [*children[: index + 1], section, *children[index + 1 :]]
            raise SectionError(f"unknown sibling section: {after!r}")

        return self._map_children(parent, place)

    def remove(self, key: str) -> Prompt:
        """Drop a section and its subtree.

        A locked section leaves the prompt unchanged; an unknown key raises
        :class:`SectionError`.
        """
        if self._require(key).locked:
            return self
        return self._map_section(key, lambda _section: None)

    def reorder(self, parent: str, order: list[str]) -> Prompt:
        """Reorder the direct children of ``parent`` (:data:`ROOT` for the top level).

        ``order`` must name exactly the existing children. A locked parent leaves the
        prompt unchanged.
        """
        if parent != ROOT:
            if self.get(parent) is None:
                raise SectionError(f"unknown parent section: {parent!r}")
            if self.is_locked(parent):
                return self

        def rearrange(children: list[Section]) -> list[Section]:
            by_key = {child.key: child for child in children}
            if sorted(order) != sorted(by_key):
                raise SectionError(f"order does not name exactly the children of {parent!r}")
            return [by_key[key] for key in order]

        return self._map_children(parent, rearrange)

    def set_enabled(self, key: str, enabled: bool) -> Prompt:
        """Enable or disable a section.

        A locked section leaves the prompt unchanged; an unknown key raises
        :class:`SectionError`.
        """
        if self._require(key).locked:
            return self
        return self._map_section(key, lambda section: _rebuild(section, enabled=enabled))

    def apply(self, patch: TraitPatch, *, registry: TraitRegistry | None = None) -> PatchResult:
        """Apply trait changes, discarding what is not admissible.

        Never raises: every change is either listed in ``applied`` or in ``rejected``.
        Changes are processed in sorted key order so the outcome is deterministic.
        """
        registry = registry if registry is not None else TraitRegistry()
        traits = dict(self.traits)
        applied: dict[str, TraitValue | None] = {}
        rejected: list[RejectedChange] = []

        for key in sorted(patch.changes):
            value = patch.changes[key]
            spec = registry.get(key)
            if not KEY_PATTERN.match(key):
                rejected.append(RejectedChange(key=key, reason="invalid_key"))
                continue
            if key in self.locked_traits or (spec is not None and spec.locked):
                rejected.append(RejectedChange(key=key, reason="locked"))
                continue
            if value is None:
                traits.pop(key, None)
                applied[key] = None
                continue
            if spec is None and not registry.allow_unknown:
                rejected.append(RejectedChange(key=key, reason="unknown_trait"))
                continue
            try:
                registry.validate_value(key, value)
            except TraitError:
                rejected.append(RejectedChange(key=key, reason="invalid_value"))
                continue
            traits[key] = value
            applied[key] = value

        prompt = self if not applied else self._with(traits=dict(sorted(traits.items())))
        return PatchResult(prompt=prompt, applied=applied, rejected=rejected)

    def check(self, registry: TraitRegistry) -> list[RejectedChange]:
        """Hold the traits this prompt already carries against a registry.

        :meth:`apply` only validates incoming changes, so a prompt outlives the specs it
        was built against: once a spec narrows its ``choices`` or changes its type, older
        prompts keep values no patch would admit today. This reports them — sorted by
        key, never raising — and reports nothing if all is well.
        """
        rejected: list[RejectedChange] = []
        for key in sorted(self.traits):
            value = self.traits[key]
            if registry.get(key) is None and not registry.allow_unknown:
                rejected.append(RejectedChange(key=key, reason="unknown_trait"))
                continue
            try:
                registry.validate_value(key, value)
            except TraitError:
                rejected.append(RejectedChange(key=key, reason="invalid_value"))
        return rejected

    # -- identity ------------------------------------------------------------

    def fingerprint(self) -> str:
        """SHA-256 over the canonical JSON of sections, traits and renderer config.

        Two prompts with the same fingerprint render identically, so identical work is
        never done twice.
        """
        payload = {
            "sections": [section.model_dump(mode="json") for section in self.sections],
            "traits": {key: self.traits[key] for key in sorted(self.traits)},
            "locked_traits": sorted(self.locked_traits),
            "renderer": self.renderer.model_dump(mode="json"),
        }
        return sha256_hex(payload)

    # -- output --------------------------------------------------------------

    def render(
        self,
        *,
        bindings: Mapping[str, str] | None = None,
        registry: TraitRegistry | None = None,
        budget: TokenBudget | None = None,
    ) -> RenderResult:
        """Compile this prompt into messages.

        The result is the **frame**, not the full conversation: a history belongs
        between the system message(s) and the final user message and is inserted by the
        calling layer. This library knows no history.
        """
        from hera_prompts.render import render_prompt

        return render_prompt(self, bindings=bindings, registry=registry, budget=budget)

    # -- internals -----------------------------------------------------------

    def _with(self, **updates: Any) -> Prompt:
        data = self.model_dump()
        data.update(updates)
        return Prompt.model_validate(data)

    def _map_section(self, key: str, fn: Callable[[Section], Section | None]) -> Prompt:
        # Callers check the key with _require first, so the section always exists here.
        sections = _map_section_in(self.sections, key, fn)[0]
        return self._with(sections=[section.model_dump() for section in sections])

    def _map_children(self, parent: str, fn: Callable[[list[Section]], list[Section]]) -> Prompt:
        if parent == ROOT:
            sections = fn(list(self.sections))
            return self._with(sections=[section.model_dump() for section in sections])
        return self._map_section(
            parent, lambda section: _rebuild(section, children=fn(list(section.children)))
        )


def _rebuild(section: Section, **updates: Any) -> Section:
    """Return a copy of ``section`` with ``updates`` applied, revalidating the subtree."""
    data = section.model_dump()
    data.update(updates)
    return Section.model_validate(data)


def _map_section_in(
    sections: list[Section], key: str, fn: Callable[[Section], Section | None]
) -> tuple[list[Section], bool]:
    result: list[Section] = []
    found = False
    for section in sections:
        if section.key == key:
            found = True
            replacement = fn(section)
            if replacement is not None:
                result.append(replacement)
            continue
        if key.startswith(f"{section.key}."):
            children, child_found = _map_section_in(list(section.children), key, fn)
            if child_found:
                found = True
                result.append(_rebuild(section, children=children))
                continue
        result.append(section)
    return result, found


class SectionChange(BaseModel):
    """A section that was added, removed, or whose fields changed."""

    model_config = ConfigDict(frozen=True)

    key: str
    kind: Literal["added", "removed", "modified"]
    fields: list[str] = Field(default_factory=list)


class TraitChange(BaseModel):
    """A trait that was added, removed or given a different value."""

    model_config = ConfigDict(frozen=True)

    key: str
    before: TraitValue | None = None
    after: TraitValue | None = None


class RendererChange(BaseModel):
    """A single renderer option that differs."""

    model_config = ConfigDict(frozen=True)

    field: str
    before: bool | str
    after: bool | str


class PromptDiff(BaseModel):
    """The difference between two prompts, kept apart by kind."""

    model_config = ConfigDict(frozen=True)

    sections: list[SectionChange] = Field(default_factory=list)
    traits: list[TraitChange] = Field(default_factory=list)
    renderer: list[RendererChange] = Field(default_factory=list)


def diff(a: Prompt, b: Prompt) -> PromptDiff:
    """Compare two prompts. All lists come out sorted by key."""
    left = _flatten(a)
    right = _flatten(b)

    sections: list[SectionChange] = []
    for key in sorted(set(left) | set(right)):
        if key not in left:
            sections.append(SectionChange(key=key, kind="added"))
        elif key not in right:
            sections.append(SectionChange(key=key, kind="removed"))
        else:
            fields = sorted(name for name, value in left[key].items() if right[key][name] != value)
            if fields:
                sections.append(SectionChange(key=key, kind="modified", fields=fields))

    traits = [
        TraitChange(key=key, before=a.traits.get(key), after=b.traits.get(key))
        for key in sorted(set(a.traits) | set(b.traits))
        if a.traits.get(key) != b.traits.get(key)
    ]

    before = a.renderer.model_dump()
    after = b.renderer.model_dump()
    renderer = [
        RendererChange(field=name, before=before[name], after=after[name])
        for name in sorted(before)
        if before[name] != after[name]
    ]

    return PromptDiff(sections=sections, traits=traits, renderer=renderer)


def _flatten(prompt: Prompt) -> dict[str, dict[str, Any]]:
    return {
        node.key: node.model_dump(mode="json", exclude={"children"})
        for root in prompt.sections
        for node in root.walk()
    }


PatchResult.model_rebuild()

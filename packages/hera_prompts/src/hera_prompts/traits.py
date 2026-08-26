"""Traits: declared specs, the registry that validates them, and patches against them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hera_prompts.canonical import sha256_hex
from hera_prompts.errors import TraitError
from hera_prompts.models import KEY_PATTERN

if TYPE_CHECKING:
    from hera_prompts.prompt import Prompt

TraitValue = bool | str | int


def matches_type(value: TraitValue, declared: Literal["str", "bool", "int"]) -> bool:
    """Check a value against a declared trait type.

    ``bool`` is a subclass of ``int`` in Python, so the two are told apart explicitly.
    """
    if declared == "bool":
        return isinstance(value, bool)
    if declared == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, str)


def format_value(value: TraitValue) -> str:
    """Render a trait value as the plain text every renderer falls back to."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class TraitSpec(BaseModel):
    """Declaration of a single trait.

    ``render`` is either a mapping from value to sentence, or a template containing
    ``{value}``. Without it — or for a trait unknown to the registry — every renderer
    falls back to the raw pair.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    type: Literal["str", "bool", "int"]
    default: TraitValue | None = None
    description: str = ""
    choices: list[TraitValue] | None = None
    render: dict[str, str] | str | None = None
    locked: bool = False

    @model_validator(mode="after")
    def _validate_spec(self) -> TraitSpec:
        if not KEY_PATTERN.match(self.key):
            raise TraitError(f"invalid trait key: {self.key!r}")
        if self.default is not None and not matches_type(self.default, self.type):
            raise TraitError(f"default of {self.key!r} does not match type {self.type!r}")
        return self

    def rendered_sentence(self, value: TraitValue) -> str | None:
        """Return the prose form of ``value``, or ``None`` when no template applies."""
        if self.render is None:
            return None
        if isinstance(self.render, str):
            return self.render.format(value=format_value(value))
        return self.render.get(format_value(value))


class TraitRegistry(BaseModel):
    """The declared set of traits.

    ``allow_unknown=True`` lets the layer above invent traits of its own;
    ``False`` restricts patches to the declared set. Both are configuration, not code.
    """

    model_config = ConfigDict(frozen=True)

    specs: list[TraitSpec] = Field(default_factory=list)
    allow_unknown: bool = True

    @model_validator(mode="after")
    def _validate_registry(self) -> TraitRegistry:
        seen: set[str] = set()
        for spec in self.specs:
            if spec.key in seen:
                raise TraitError(f"duplicate trait spec: {spec.key!r}")
            seen.add(spec.key)
        return self

    def get(self, key: str) -> TraitSpec | None:
        """Return the spec for ``key``, or ``None`` when the trait is undeclared."""
        for spec in self.specs:
            if spec.key == key:
                return spec
        return None

    def validate_value(self, key: str, value: TraitValue) -> None:
        """Raise :class:`TraitError` when ``value`` is not admissible for ``key``."""
        spec = self.get(key)
        if spec is None:
            if self.allow_unknown:
                return
            raise TraitError(f"unknown trait: {key!r}")
        if not matches_type(value, spec.type):
            raise TraitError(
                f"trait {key!r} expects type {spec.type!r}, got {type(value).__name__}"
            )
        if spec.choices is not None and value not in spec.choices:
            raise TraitError(f"trait {key!r} does not admit value {value!r}")

    def defaults(self) -> dict[str, TraitValue]:
        """The declared defaults as a plain mapping.

        Deliberately *not* applied during rendering: a prompt whose behaviour comes half
        from its own state and half from a registry would be a prompt where setting a
        trait to ``None`` does not delete it but falls back to the default — a deletion
        that silently does nothing. The layer above materialises these into the prompt
        once, so that what takes effect is what the object says.
        """
        return {spec.key: spec.default for spec in self.specs if spec.default is not None}

    def fingerprint(self) -> str:
        """SHA-256 over the canonical JSON of the specs, in declaration order.

        Order is part of the identity because it is part of the output: the declared
        order decides the order traits render in.
        """
        payload = {
            "allow_unknown": self.allow_unknown,
            "specs": [spec.model_dump(mode="json") for spec in self.specs],
        }
        return sha256_hex(payload)


class TraitPatch(BaseModel):
    """A set of trait changes. A value of ``None`` deletes the trait."""

    model_config = ConfigDict(frozen=True)

    changes: dict[str, TraitValue | None]
    rationale: str | None = None


class RejectedChange(BaseModel):
    """A single change that was discarded, with the reason why."""

    model_config = ConfigDict(frozen=True)

    key: str
    reason: Literal["locked", "unknown_trait", "invalid_value", "invalid_key"]


class PatchResult(BaseModel):
    """Outcome of :meth:`Prompt.apply`.

    Applying a patch never raises on a rejected change: a caller that keeps touching
    locked traits is a signal the layer above wants to see, and aborting would kill an
    entire run instead.
    """

    model_config = ConfigDict(frozen=True)

    prompt: Prompt
    applied: dict[str, TraitValue | None]
    rejected: list[RejectedChange]

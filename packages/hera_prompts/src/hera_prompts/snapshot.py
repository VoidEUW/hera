"""What a rendering produced, and what it was produced from."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from hera_prompts.models import Message, RendererConfig
from hera_prompts.traits import TraitValue


class PromptSnapshot(BaseModel):
    """A record of one rendering — a plain model without a table; persisting it is the
    job of the application layer.

    Three fields explain missing content, and they are kept apart on purpose:
    ``dropped_keys`` for sections removed under budget pressure, ``unbound_slots`` for
    slots no binding filled, and ``RenderResult.unused_bindings`` for bindings that
    matched no slot.
    """

    model_config = ConfigDict(frozen=True)

    content_hash: str
    prompt_fingerprint: str
    registry_fingerprint: str | None = None
    renderer: RendererConfig
    traits: dict[str, TraitValue] = Field(default_factory=dict)
    dropped_keys: list[str] = Field(default_factory=list)
    unbound_slots: list[str] = Field(default_factory=list)
    token_estimate: int = 0
    component_versions: dict[str, UUID] = Field(default_factory=dict)


class RenderResult(BaseModel):
    """The compiled messages plus the snapshot that explains them.

    ``messages`` is the **frame**, not the whole conversation: a history belongs between
    the system message(s) and the final user message and is inserted by the calling
    layer. This library knows no history.
    """

    model_config = ConfigDict(frozen=True)

    messages: list[Message]
    snapshot: PromptSnapshot
    unused_bindings: list[str] = Field(default_factory=list)

"""Rendering: prompt object plus bindings in, messages out."""

from __future__ import annotations

from collections.abc import Mapping

from hera_prompts.canonical import sha256_hex
from hera_prompts.errors import BudgetExceeded
from hera_prompts.models import Message
from hera_prompts.prompt import Prompt
from hera_prompts.render.base import (
    Block,
    Plan,
    Renderer,
    TraitLine,
    build_plan,
    next_drop_candidate,
    to_messages,
    unbound_slots,
    used_slots,
)
from hera_prompts.render.budget import TokenBudget, estimate_tokens
from hera_prompts.render.keyvalue import KeyValueRenderer
from hera_prompts.render.markdown import MarkdownRenderer
from hera_prompts.render.xml import XmlRenderer
from hera_prompts.snapshot import PromptSnapshot, RenderResult
from hera_prompts.traits import TraitRegistry

RENDERERS: dict[str, Renderer] = {
    "keyvalue": KeyValueRenderer(),
    "xml": XmlRenderer(),
    "markdown": MarkdownRenderer(),
}

__all__ = [
    "RENDERERS",
    "Block",
    "KeyValueRenderer",
    "MarkdownRenderer",
    "Plan",
    "Renderer",
    "TokenBudget",
    "TraitLine",
    "XmlRenderer",
    "build_plan",
    "estimate_tokens",
    "render_prompt",
]


def render_prompt(
    prompt: Prompt,
    *,
    bindings: Mapping[str, str] | None = None,
    registry: TraitRegistry | None = None,
    budget: TokenBudget | None = None,
) -> RenderResult:
    """Compile ``prompt`` into messages.

    Under budget pressure sections are dropped by ascending priority and the rendering
    is repeated until it fits; what was dropped ends up in ``dropped_keys``, so a poor
    answer can later be traced back to content that was missing.
    """
    bindings = dict(bindings or {})
    effective_registry = registry if registry is not None else TraitRegistry()
    renderer = RENDERERS[prompt.renderer.format]
    counter = budget.counter if budget is not None else estimate_tokens

    dropped: list[str] = []
    while True:
        plan = build_plan(prompt, bindings, effective_registry, frozenset(dropped))
        messages = to_messages(plan, prompt.renderer, renderer)
        estimate = sum(counter(message.content) for message in messages)
        if budget is None or estimate <= budget.available:
            break
        candidate = next_drop_candidate(plan)
        if candidate is None:
            raise BudgetExceeded(
                f"rendering needs {estimate} tokens, budget allows {budget.available} "
                "and nothing further may be dropped"
            )
        dropped.append(candidate)

    snapshot = PromptSnapshot(
        content_hash=_content_hash(messages),
        prompt_fingerprint=prompt.fingerprint(),
        registry_fingerprint=registry.fingerprint() if registry is not None else None,
        renderer=prompt.renderer,
        traits=dict(prompt.traits),
        dropped_keys=dropped,
        unbound_slots=unbound_slots(prompt, bindings),
        token_estimate=estimate,
    )
    return RenderResult(
        messages=messages,
        snapshot=snapshot,
        unused_bindings=sorted(set(bindings) - used_slots(prompt)),
    )


def _content_hash(messages: list[Message]) -> str:
    return sha256_hex([message.model_dump(mode="json") for message in messages])

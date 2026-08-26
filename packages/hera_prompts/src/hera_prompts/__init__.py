"""hera_prompts — a prompt compiler.

Holds structured, serialisable prompt state and compiles it into ready-made messages
for a language model. It knows nothing about tools, memories, skills or chats: foreign
content enters exclusively as pre-rendered strings through named slots.
"""

from __future__ import annotations

from hera_prompts.errors import (
    BudgetExceeded,
    MissingBinding,
    PromptError,
    SectionError,
    TraitError,
)
from hera_prompts.models import Message, RendererConfig, Role, Section
from hera_prompts.prompt import (
    ROOT,
    Prompt,
    PromptDiff,
    RendererChange,
    SectionChange,
    TraitChange,
    diff,
)
from hera_prompts.render.budget import TokenBudget, estimate_tokens
from hera_prompts.snapshot import PromptSnapshot, RenderResult
from hera_prompts.traits import (
    PatchResult,
    RejectedChange,
    TraitPatch,
    TraitRegistry,
    TraitSpec,
    TraitValue,
)

__all__ = [
    "ROOT",
    "BudgetExceeded",
    "Message",
    "MissingBinding",
    "PatchResult",
    "Prompt",
    "PromptDiff",
    "PromptError",
    "PromptSnapshot",
    "RejectedChange",
    "RenderResult",
    "RendererChange",
    "RendererConfig",
    "Role",
    "Section",
    "SectionChange",
    "SectionError",
    "TokenBudget",
    "TraitChange",
    "TraitError",
    "TraitPatch",
    "TraitRegistry",
    "TraitSpec",
    "TraitValue",
    "diff",
    "estimate_tokens",
]

"""Error hierarchy of the library.

None of these derive from ``ValueError`` on purpose: raising them inside a pydantic
validator must surface the error itself instead of a wrapped ``ValidationError``.
"""

from __future__ import annotations


class PromptError(Exception):
    """Base class for every error raised by ``hera_prompts``."""


class SectionError(PromptError):
    """Invalid key, duplicate key, or a section carrying both content and slot."""


class TraitError(PromptError):
    """Unknown trait under a closed registry, wrong type, or a value outside ``choices``."""


class MissingBinding(PromptError):
    """A required section refers to a slot for which no binding was supplied."""


class BudgetExceeded(PromptError):
    """The rendering exceeds the token budget and nothing droppable is left."""

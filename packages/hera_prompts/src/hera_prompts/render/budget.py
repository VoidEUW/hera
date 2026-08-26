"""Token budget: how much room the rendering may take, and how much to keep free."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field


def estimate_tokens(text: str) -> int:
    """Default counter — roughly three characters per token. No tokenizer here.

    Three, not four, because the two errors are not symmetric: an underestimate lets the
    budget bite too late and the call runs into the context limit, while an overestimate
    drops one section too early, which is visible and harmless. German text with its long
    compounds sits closer to three anyway. Pass a real tokenizer as ``counter`` when the
    exact number matters.
    """
    return len(text) // 3


class TokenBudget(BaseModel):
    """A limit on the rendered size.

    Not part of :class:`~hera_prompts.prompt.Prompt`: it is passed to ``render()``,
    because ``counter`` is a callable and therefore not serialisable.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    limit: int
    counter: Callable[[str], int] = Field(default=estimate_tokens)
    reserve: int = 0

    @property
    def available(self) -> int:
        """The room actually left for the prompt once the reserve is set aside."""
        return self.limit - self.reserve

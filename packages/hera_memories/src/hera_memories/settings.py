"""What a deployment may change about memory.

One number, and it is the one the whole design turns on: every enabled memory is in the system
prompt, so the only thing standing between *she remembers everything* and *a turn that fails at
the endpoint's context limit* is this ceiling.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class MemoriesSettings(BaseSettings):
    """Read from ``HERA_MEMORIES_*``."""

    model_config = SettingsConfigDict(env_prefix="HERA_MEMORIES_", extra="ignore")

    budget_tokens: int = 4_000
    """How much of the prompt her memories may take.

    Four thousand is a deliberate middle: enough for a few dozen real facts about a person and
    their work, and small enough that it stays a minority of a 32k window once a skill body, six
    rounds of history and a tool catalogue are also in there. It is a *steering* number, not a
    safety margin — the number that keeps a turn from failing is the endpoint's own limit, and
    this one keeps memory from being the reason it is reached.

    Measured in the approximation :data:`hera_memories.models.CHARS_PER_TOKEN` describes, which
    is why it is not also a promise about the context window.
    """

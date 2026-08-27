"""How a turn behaves, from ``HERA_CHATS_*`` environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatsSettings(BaseSettings):
    """Boot settings for the turn orchestrator."""

    model_config = SettingsConfigDict(env_prefix="HERA_CHATS_", extra="ignore")

    model: str = "qwen3.6-35b"
    """The one model (ADR 2). A name rather than a choice: what varies between deployments is
    what the local server calls it, not which family it belongs to."""

    max_iterations: int = 8
    """How many times the model may be called in one turn before the loop is cut.

    A turn goes round once per batch of tool calls. Eight is generous for real work and low
    enough that a model stuck calling the same tool costs seconds rather than a rate limit.
    Hitting it closes the turn with ``max_iterations``, which is visible in the interface —
    silently stopping would look like she simply gave a short answer.
    """

    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None

    title_length: int = 60
    """How much of the first message becomes the chat's title in the sidebar."""

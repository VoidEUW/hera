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

    asking_tools: tuple[str, ...] = ()
    """Qualified names of tools that are answered by a *person* rather than run.

    A call to one of these suspends the turn: the question is recorded, the turn closes with
    ``awaiting_answer``, and replying resumes the same message with the reply as that call's
    result. Empty by default, which means nothing suspends — this package does not know which
    tools exist and emphatically does not know which of them are hers.

    Configured by the application, from ``hera_mcp.ASK_TOOL``. A setting rather than a hardcoded
    ``"hera__ask"`` for the reason the layering rule exists: ``hera_chats`` naming a tool on her
    own server would be this package learning what Hera *is*, and the next such tool would be a
    second string in a second place.
    """

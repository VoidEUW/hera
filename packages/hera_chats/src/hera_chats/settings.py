"""How a turn behaves, from ``HERA_CHATS_*`` environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from hera_chats.history import MAX_ARGUMENT_CHARS


class ChatsSettings(BaseSettings):
    """Boot settings for the turn orchestrator."""

    model_config = SettingsConfigDict(env_prefix="HERA_CHATS_", extra="ignore")

    model: str = "qwen3.6-35b"
    """The one model (ADR 2). A name rather than a choice: what varies between deployments is
    what the local server calls it, not which family it belongs to."""

    max_iterations: int = 12
    """How many rounds of tool calls one turn may take before the budget is spent.

    A turn goes round once per batch. Twelve rather than the original eight because real
    research legitimately takes more than eight searches — and because a model that was
    *wasting* its budget on repeats now cannot: see :attr:`repeat_limit`, which is the fix for
    the loop this number used to be the only guard against.

    Spending it no longer ends the turn mid-thought. The model gets one last round with the
    tools withheld, so it answers with what it has; the turn still closes with
    ``max_iterations``, because "she stopped looking and summarised" is a different thing from
    "she finished" and the interface should say so.
    """

    repeat_limit: int = 2
    """How many times one identical call — same tool, same arguments — may run in a turn.

    The observed failure this exists for: asked for a figure it could not find, the model ran
    the *same* search four times, spent its whole budget on it, and was cut off mid-sentence.
    Nothing in the loop noticed, because each call succeeded — they simply did not contain the
    answer.

    Two rather than one, because the turn cannot know which tools are idempotent. Reading a
    file after writing it is the same call with a legitimately different result, and refusing
    the second would break it; a *third* identical call inside one turn is a loop in every case
    worth designing for. Refused calls come back as a result the model can read, quoting what
    the call returned last time — so it is told the words did not work rather than left to
    wonder why nothing changed.
    """

    max_history_argument_chars: int = MAX_ARGUMENT_CHARS
    """How much of one string argument is replayed into a later turn's history.

    A tool whose argument is a whole document — a page she published, a file she wrote to her
    scratchpad — would otherwise sit in the prompt of every question that follows it, so a
    conversation grows by the size of everything she has ever written and the ceiling arrives
    without anybody doing anything unusual.

    Nothing is lost: the call went out whole, the event stores it whole, the interface shows it
    whole, and she can read the file back. ``0`` turns the shortening off.
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

    chat_meta_key: str = ""
    """Where a tool call is told which conversation it belongs to (ADR 12).

    A key, not a value: the turn knows the chat and the tool layer knows how to carry a mapping,
    and this is the word the two agree on. Set, every dispatch in the turn goes out with
    ``{chat_meta_key: <chat id>}`` in the call's ``_meta``; empty — the default — sends nothing,
    which is a deployment where no tool asks which conversation it is in rather than a broken
    one.

    The same shape as :attr:`asking_tools` and for the same reason. ``hera_mcp.CHAT_ID_META`` is
    where the string is written; this package must not learn it, because ``hera_tools`` carries
    the mapping opaquely and ``hera_mcp`` reads it, and neither may import the other.
    """

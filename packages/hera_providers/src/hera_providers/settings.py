"""Boot settings for reaching a model endpoint."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderSettings(BaseSettings):
    """Read from ``HERA_PROVIDER_*`` environment variables.

    The defaults describe the intended deployment: a local OpenAI-compatible server on the
    same machine, no authentication, one Qwen model.
    """

    model_config = SettingsConfigDict(env_prefix="HERA_PROVIDER_")

    base_url: str = "http://localhost:1234/v1"
    api_key: str = ""
    model: str = "qwen3.6-35b"
    embedding_model: str = ""
    """Empty means embeddings are off; retrieval then falls back to keyword overlap."""

    timeout_s: float = 600.0
    """How long the endpoint may be **silent**, not how long a turn may take.

    This is httpx's read timeout, and on a streamed completion it is measured between one piece
    of the response and the next — so once tokens are flowing it is never near being spent, and
    a turn that takes twenty minutes to write a long document is not affected by it at all. What
    it actually bounds is the *quiet* part: loading the weights on the first request, and
    prefilling a prompt that has grown a skill body, a scratchpad and six rounds of history in
    it. Both of those are silence, and neither is a fault.

    Ten minutes rather than the three it started at, because three was not enough: a local 35B
    asked for a whole HTML page part-way through a long conversation fell off the end of it, and
    what a person saw was ``did not answer in time`` under an answer that had been going fine.
    A model that is thinking and a model that has stopped look identical from here, so the
    number has to be generous enough that hitting it means something is genuinely wrong — and
    the turn is stoppable from the composer the whole time it is running, which is the reason
    a long ceiling costs nothing.
    """

    connect_timeout_s: float = 5.0
    """Short on purpose: "nothing is listening" should be answered immediately, not after
    ten minutes of the read timeout above. This is the one that catches a wrong port."""

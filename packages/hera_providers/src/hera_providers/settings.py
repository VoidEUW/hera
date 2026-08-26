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

    timeout_s: float = 180.0
    """Generous on purpose: a local server may load a 35B model on the first request, and a
    turn that fails because the weights were cold is a worse outcome than one that waits."""

    connect_timeout_s: float = 5.0
    """Short on purpose: "nothing is listening" should be answered immediately, not after
    three minutes of the read timeout above."""

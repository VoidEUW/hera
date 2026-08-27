"""The model boundary.

Everything that knows how to talk to a language model lives here, and nothing that knows what
a chat, a prompt or a tool *is*. What leaves this package is one normalised event union --
see :mod:`hera_providers.events`, which is the contract the rest of the system is built on.
"""

from __future__ import annotations

from hera_providers.base import EmbeddingProvider, Provider, StreamAdapter
from hera_providers.errors import (
    MalformedResponse,
    ProviderError,
    ProviderHTTPError,
    ProviderTimeout,
    ProviderUnavailable,
    StreamInterrupted,
)
from hera_providers.events import (
    EVENT_ADAPTER,
    Event,
    FinishReason,
    TextDelta,
    ThinkingDelta,
    ToolCallReady,
    TurnEnd,
    Usage,
)
from hera_providers.fake import (
    FakeProvider,
    FakeProviderExhausted,
    pseudo_embedding,
    text_turn,
    thinking_turn,
    tool_call,
    tool_turn,
)
from hera_providers.openai import OpenAICompatibleProvider, build_client, chat_payload
from hera_providers.qwen import QwenAdapter
from hera_providers.request import (
    ChatMessage,
    ChatRequest,
    ContentPart,
    ImagePart,
    Role,
    TextPart,
    ToolCall,
    ToolSpec,
)
from hera_providers.settings import ProviderSettings

__all__ = [
    "EVENT_ADAPTER",
    "ChatMessage",
    "ChatRequest",
    "ContentPart",
    "EmbeddingProvider",
    "Event",
    "FakeProvider",
    "FakeProviderExhausted",
    "FinishReason",
    "ImagePart",
    "MalformedResponse",
    "OpenAICompatibleProvider",
    "Provider",
    "ProviderError",
    "ProviderHTTPError",
    "ProviderSettings",
    "ProviderTimeout",
    "ProviderUnavailable",
    "QwenAdapter",
    "Role",
    "StreamAdapter",
    "StreamInterrupted",
    "TextDelta",
    "TextPart",
    "ThinkingDelta",
    "ToolCall",
    "ToolCallReady",
    "ToolSpec",
    "TurnEnd",
    "Usage",
    "build_client",
    "chat_payload",
    "pseudo_embedding",
    "text_turn",
    "thinking_turn",
    "tool_call",
    "tool_turn",
]

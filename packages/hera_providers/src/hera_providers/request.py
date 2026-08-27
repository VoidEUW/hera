"""The request side: what gets sent to a model.

Deliberately its own vocabulary rather than a re-export of ``hera_prompts.Message``. The two
packages sit side by side at the foundation and import nothing of each other's, and they
describe different things: ``hera_prompts`` compiles the *frame* of a prompt, while a request
carries a whole conversation including assistant turns and tool results. The layer that owns
the turn maps one onto the other -- that mapping is where the history goes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    """Every role an OpenAI-compatible endpoint accepts.

    ``DEVELOPER`` is here because ``hera_prompts`` can emit it; whether a given server honours
    it or quietly folds it into the system message is the server's business, and the prompt
    compiler's default avoids the question by folding it itself.
    """

    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """A tool call being sent *back* as part of an assistant turn.

    The mirror image of :class:`~hera_providers.events.ToolCallReady`: that one comes out of a
    stream, this one goes into the next request so the model can see what it asked for.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class TextPart(BaseModel):
    """Prose, in a message that is carrying more than prose."""

    model_config = ConfigDict(frozen=True)

    type: Literal["text"] = "text"
    text: str = ""


class ImagePart(BaseModel):
    """A picture in a user message.

    ``url`` is a ``data:`` URL for something read off a person's disk, or an ``http(s)`` one for
    something already on the network. This package does not care which — it moves whichever it
    is onto the wire — but a local endpoint that cannot fetch is the reason the interface sends
    the bytes rather than a link.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["image_url"] = "image_url"
    url: str
    detail: Literal["auto", "low", "high"] | None = None


ContentPart = Annotated[TextPart | ImagePart, Field(discriminator="type")]
"""One block of a multi-part message. Deliberately small: text and images are what an
OpenAI-compatible endpoint agrees on, and a part this package invented would be a part no
server understands."""


class ChatMessage(BaseModel):
    """One message in the conversation being sent.

    ``content`` is a plain string in the ordinary case and a list of parts when the message
    carries something that is not prose — today, a picture. Both are what the protocol accepts,
    and the string is kept rather than always sending a one-element list because a good number
    of local servers only ever grew the string form.

    A ``TOOL`` message carries the result of a call and must set ``tool_call_id`` to the id of
    the call it answers; a model that cannot match the two ignores the result.
    """

    model_config = ConfigDict(frozen=True)

    role: Role
    content: str | list[ContentPart] = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None

    @property
    def text(self) -> str:
        """The prose of this message, whichever form the content is in.

        Anything reading a message for its *words* — a title, a budget, a log line — wants this
        rather than ``content``, so that a message growing a picture does not turn every such
        reader into a type check.
        """
        if isinstance(self.content, str):
            return self.content
        return "".join(part.text for part in self.content if isinstance(part, TextPart))


class ToolSpec(BaseModel):
    """A tool offered to the model, in JSON Schema.

    ``hera_tools`` builds these from the MCP catalogue. Nothing here validates the schema --
    it is the server's to define and the model's to satisfy.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})


class ChatRequest(BaseModel):
    """One call to a model.

    ``extra`` is merged into the request body last and is the seam for anything a particular
    server understands and this package does not need to know about -- ``reasoning_effort``,
    a sampler setting, a vendor flag. Guessing at those fields here would put provider
    specifics in the shared vocabulary, which is the thing this package exists to prevent.
    """

    model_config = ConfigDict(frozen=True)

    model: str
    messages: list[ChatMessage]
    tools: list[ToolSpec] = Field(default_factory=list)
    tool_choice: Literal["auto", "none", "required"] = "auto"
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

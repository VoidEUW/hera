"""Hera's own capabilities, as an MCP server like any other.

``emotion``, ``remember``, ``note`` and ``skill`` are not privileged. They are registered on a
real :class:`~mcp.server.mcpserver.MCPServer`, reached over an in-memory transport by the same
client the filesystem server is reached by, listed in the same catalogue, and checked by the
same permission policy. ADR 4 asked for that on the grounds that a special case here would
have to be unpicked in v0.3, when this server is exposed to other agents -- at which point the
only change should be which transport it is served over.

The tool descriptions are prompt text. The model reads them and nothing else explains what
these do, so they are written for it: short, imperative, and clear about when *not* to call.

Failures here raise ``ToolError`` rather than anything else, and that is not a detail: the SDK
passes a ``ToolError`` message through to the model as the content of a failed result, and
replaces every other exception with "Error executing tool <name>" so that a crash cannot leak
internals. Everything raised in this module is written to be read by the model, so it has to be
the kind that survives.
"""

from __future__ import annotations

from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from hera_tools.ports import MemoryWriter, NoteWriter, SkillLibrary

BUILTIN_SERVER_NAME = "hera"
"""Her tools are namespaced ``hera__emotion``, ``hera__remember`` and so on."""

EMOTION_KINDS = (
    "agree",
    "disagree",
    "doubt",
    "surprised",
    "funny",
    "joke",
    "warn",
    "ask",
    "curious",
    "hope",
    "excited",
    "sorry",
    "annoyed",
    "judge",
)
"""The starter vocabulary, documented in the ``emotions`` mind region.

Repeated in the tool description as examples rather than as an enumeration. ADR 3 is explicit
that ``kind`` is free text and that an unknown kind renders with a fallback icon; a model that
hard-obeys its schema will never invent one if the schema says it may not, and the freedom has
to be granted where the model can see it.
"""


def build_builtin_server(
    *,
    memories: MemoryWriter | None = None,
    notes: NoteWriter | None = None,
    skills: SkillLibrary | None = None,
    version: str = "0.1.0",
) -> MCPServer:
    """Assemble the in-process server, wired to whichever ports this deployment has.

    Everything is optional. What is missing still appears in the catalogue and answers with a
    tool error saying it is unavailable -- better than vanishing, because a model that cannot
    see ``remember`` concludes it cannot remember, and says so to the person.
    """
    server: MCPServer = MCPServer(BUILTIN_SERVER_NAME, title="Hera", version=version)

    @server.tool(
        name="emotion",
        title="Show a stance",
        description=(
            "Show how you feel about what you are saying, as a small card next to your answer. "
            "Call it alongside your prose, as often as it is honest to -- several in one turn "
            "is normal. `kind` is a short lowercase word and you may invent one: "
            f"{', '.join(EMOTION_KINDS)} are examples, not the whole set. `text` is the one "
            "line that goes on the card; leave it out for a card that is only a stance."
        ),
    )
    def emotion(kind: str, text: str = "") -> str:
        """Acknowledged and nothing more.

        The tool call *is* the record: it is persisted as an event and the interface renders
        it. Returning anything substantial would only spend tokens on the way back in.
        """
        return "shown"

    @server.tool(
        name="remember",
        title="Remember a fact",
        description=(
            "Store something worth knowing in the future: a preference, a decision, a fact "
            "about the person or the project. Use `scope='global'` for what stays true beyond "
            "this conversation and `scope='chat'` for what only holds here. Do not store "
            "guesses, or what is already in the conversation you can see."
        ),
    )
    async def remember(text: str, scope: Literal["global", "chat"] = "global") -> str:
        if memories is None:
            raise ToolError("memory is not available in this deployment")
        return await memories.remember(text, scope=scope)

    @server.tool(
        name="note",
        title="Write a note",
        description=(
            "Write a document into the notes the person keeps -- a summary, a plan, a piece of "
            "collected research. This is a file they will read later, not a memory of yours; "
            "for a fact about them, use `remember` instead."
        ),
    )
    async def note(text: str, title: str = "") -> str:
        if notes is None:
            raise ToolError("notes are not available in this deployment")
        return await notes.write_note(text, title=title)

    @server.tool(
        name="skill",
        title="Load a skill",
        description=(
            "Load the full instructions of a named skill. Whatever applies to this turn has "
            "already been given to you, so reach for this only when the work has moved on to "
            "something else and you know the name you want."
        ),
    )
    async def skill(name: str) -> str:
        if skills is None:
            raise ToolError("skills are not available in this deployment")
        body = await skills.load(name)
        if body is None:
            available = ", ".join(await skills.names()) or "none"
            raise ToolError(f"no skill named {name!r}; available: {available}")
        return body

    return server

"""The MCP server Hera **is**, as opposed to the ones she can reach.

Her own tools — ``emotion``, ``ask``, ``remember``, ``note``, ``skill``, ``search``, the
scratchpad she thinks on and the artifacts she publishes — on a real
:class:`~mcp.server.mcpserver.MCPServer`. The application mounts it in-process through
``hera_tools``, which reaches it with the same client it reaches a filesystem server with, lists
it in the same catalogue and checks it with the same policy (ADR 4).

Its own package because it is its own thing. ``hera_tools`` is the **client** — lifecycle,
namespacing, dispatch, the parts that are true of anybody's MCP server. This is the **server**,
and everything in it is a statement about what Hera can do: the emotion vocabulary, what
``remember`` is for, the sentence the model reads before deciding to call ``note``. Those change
for reasons that have nothing to do with subprocess lifetimes, and in v0.3 this is what gets
served over a transport of its own so Claude Code can attach to her.

It imports no other ``hera_*`` package and never will. What it needs from the rest of the system
arrives as :mod:`hera_mcp.ports`.
"""

from __future__ import annotations

from hera_mcp.emotions import DEFAULT_EMOTIONS, Emotion, Tone, render_emotions
from hera_mcp.ports import (
    Artifacts,
    Hit,
    MemoryWriter,
    NoteWriter,
    ScratchFile,
    Scratchpad,
    Searcher,
    SkillLibrary,
)
from hera_mcp.server import (
    ARTIFACT_META,
    ASK_TOOL,
    BUILTIN_SERVER_NAME,
    CHAT_ID_META,
    SCRATCH_LISTING_LIMIT,
    SEARCH_LIMIT,
    TOOL_NAMES,
    build_builtin_server,
)

__all__ = [
    "ARTIFACT_META",
    "ASK_TOOL",
    "BUILTIN_SERVER_NAME",
    "CHAT_ID_META",
    "DEFAULT_EMOTIONS",
    "SCRATCH_LISTING_LIMIT",
    "SEARCH_LIMIT",
    "TOOL_NAMES",
    "Artifacts",
    "Emotion",
    "Hit",
    "MemoryWriter",
    "NoteWriter",
    "ScratchFile",
    "Scratchpad",
    "Searcher",
    "SkillLibrary",
    "Tone",
    "build_builtin_server",
    "render_emotions",
]

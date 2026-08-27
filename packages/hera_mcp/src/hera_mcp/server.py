"""Hera's own capabilities, as an MCP server like any other.

``emotion``, ``remember``, ``note`` and ``skill`` are not privileged. They are registered on a
real :class:`~mcp.server.mcpserver.MCPServer`, reached over an in-memory transport by the same
client the filesystem server is reached by, listed in the same catalogue, and checked by the
same permission policy. ADR 4 asked for that on the grounds that a special case here would
have to be unpicked in v0.3, when this server is exposed to other agents -- at which point the
only change should be which transport it is served over.

``remember`` and ``note`` are **unwired in v0.1**, and deliberately so: the first waits for
``hera_memories`` and the second for somewhere to write notes. Both still appear in the
catalogue and answer "not available in this deployment", because a model that cannot see
``remember`` concludes it cannot remember and tells the person so.

``search`` is the one tool here that leaves the machine, and the only one whose absence changes
what she *says* rather than what she can do: a model with no way to look something up does not
answer "I cannot check that", it guesses fluently. It takes a :class:`~hera_mcp.ports.Searcher`
like the rest -- which engine a person's questions are sent to is a decision for the deployment,
and this package does not make it.

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

from hera_mcp.ports import Hit, MemoryWriter, NoteWriter, Searcher, SkillLibrary

BUILTIN_SERVER_NAME = "hera"
"""Her tools are namespaced ``hera__emotion``, ``hera__remember`` and so on.

The name travels on the server object rather than being agreed on twice: ``hera_tools`` mounts
whatever it is handed under ``server.name``, so this constant is the only place the word is
written and renaming her server does not need the client's permission.
"""

TOOL_NAMES = ("emotion", "remember", "note", "skill", "search")
"""What this server offers, in the order they were added. Qualified, that is ``hera__emotion``
and its siblings — the ones a catalogue reports for the ``hera`` server, which is the question
a settings screen showing "5 tools" leaves a person asking."""

SEARCH_LIMIT = 20
"""The most results one call may ask for. A ceiling rather than a preference: a model that asks
for a hundred gets a page of snippets where the answer used to be, and pays for it twice --
once in the context window and once in how hard its own answer is to find afterwards."""


def build_builtin_server(
    *,
    memories: MemoryWriter | None = None,
    notes: NoteWriter | None = None,
    skills: SkillLibrary | None = None,
    searcher: Searcher | None = None,
    version: str = "0.1.0",
) -> MCPServer:
    """Assemble the in-process server, wired to whichever ports this deployment has.

    Everything is optional. What is missing still appears in the catalogue and answers with a
    tool error saying it is unavailable -- better than vanishing, because a model that cannot
    see ``remember`` concludes it cannot remember, and says so to the person.
    """
    server: MCPServer = MCPServer(BUILTIN_SERVER_NAME, title="Hera", version=version)

    # The vocabulary is deliberately *not* enumerated here. A description is fixed when the
    # server is built, and a list a person can edit on screen has to apply on the next turn
    # rather than the next restart -- so it travels in the prompt, which is assembled per turn.
    # See hera_mcp.emotions.
    @server.tool(
        name="emotion",
        title="Show a stance",
        description=(
            "Show how you feel about what you are saying, as a small card next to your "
            "answer. Call it alongside your prose, as often as it is honest to -- several in "
            "one turn is normal. `kind` is a short lowercase word; the stances you can reach "
            "for are listed in your instructions, and you may invent one when none of them is "
            "honest. `text` is the one line that goes on the card; leave it out for a card "
            "that is only a stance."
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

    @server.tool(
        name="search",
        title="Search the web",
        description=(
            "Look something up on the web. Use it whenever the answer depends on what is "
            "true now rather than on what you were trained on -- a version number, a release, "
            "an error message, anything about a person or a project you were not told about. "
            "Prefer it to guessing: an answer you invented is worse than a search that found "
            "nothing. `query` is what you would type into a search engine, not a sentence "
            "addressed to one. You get titles, links and the snippet the engine wrote; open "
            "nothing and cite the link when what you say rests on it."
        ),
    )
    async def search(query: str, limit: int = 5) -> str:
        if searcher is None:
            raise ToolError("search is not available in this deployment")
        asked = query.strip()
        if not asked:
            raise ToolError("a search needs something to search for")
        try:
            hits = await searcher.search(asked, limit=max(1, min(limit, SEARCH_LIMIT)))
        except Exception as cause:
            # Broad on purpose, and it does not hide anything: without this the SDK replaces
            # whatever came out with "Error executing tool search", which tells her nothing to
            # act on. An engine that is rate-limiting and an engine that is down want different
            # next moves, and she can only choose one if the reason survives.
            raise ToolError(f"the search failed: {cause}") from cause
        if not hits:
            # Not a ToolError: nothing was wrong. A failed result would tell her the search is
            # broken, and she would stop using it rather than try different words.
            return f"no results for {asked!r}"
        return "\n\n".join(_result(index, hit) for index, hit in enumerate(hits, start=1))

    return server


def _result(index: int, hit: Hit) -> str:
    """One result, as the model reads it.

    Numbered, because she refers back to them ("the second result") and because a wall of
    untitled snippets is the shape that makes a model quote the wrong page. The URL is on its
    own line so it survives being copied out of an answer.
    """
    lines = [f"{index}. {hit.title}".rstrip(), hit.url]
    if hit.snippet:
        lines.append(hit.snippet)
    return "\n".join(lines)

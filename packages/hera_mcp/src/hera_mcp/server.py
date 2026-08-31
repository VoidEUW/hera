"""Hera's own capabilities, as an MCP server like any other.

``emotion``, ``remember``, ``note`` and ``skill`` are not privileged. They are registered on a
real :class:`~mcp.server.mcpserver.MCPServer`, reached over an in-memory transport by the same
client the filesystem server is reached by, listed in the same catalogue, and checked by the
same permission policy. ADR 4 asked for that on the grounds that a special case here would
have to be unpicked in v0.3, when this server is exposed to other agents -- at which point the
only change should be which transport it is served over.

``note`` is **unwired**, and deliberately so: it waits for somewhere to write notes. It still
appears in the catalogue and answers "not available in this deployment", because a model that
cannot see a tool concludes it cannot do the thing and tells the person so.

``remember`` and ``forget`` are the memory pair, and what is *missing* beside them is the design
(ADR 16). There is no tool that lists memories, because every enabled one is already in her
prompt — reading them back would spend the context window on what is already in it. And
``forget`` does not delete: it switches a memory off and keeps the file, so nothing a person
told her is discarded without a person present.

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

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

from hera_mcp.ports import (
    Artifacts,
    Hit,
    Memories,
    NoteWriter,
    Scratchpad,
    Searcher,
    SkillLibrary,
)

BUILTIN_SERVER_NAME = "hera"
"""Her tools are namespaced ``hera__emotion``, ``hera__remember`` and so on.

The name travels on the server object rather than being agreed on twice: ``hera_tools`` mounts
whatever it is handed under ``server.name``, so this constant is the only place the word is
written and renaming her server does not need the client's permission.
"""

ASK_TOOL = "ask"
"""The one tool here that is answered by a *person* rather than run.

Named as a constant because the layer that suspends the turn has to recognise it, and that
layer is ``hera_chats``, which does not import this package and must not learn what her tools
are. The application reads this and configures ``ChatsSettings.asking_tools`` with the
qualified name, so the string is written once and travels rather than being agreed on twice.
"""

CHAT_ID_META = "hera/chatId"
"""Where a call says which conversation it belongs to (ADR 12).

A key in the request's ``_meta``, not an argument: the model chooses arguments, so a ``chat_id``
in the schema would be one the model invents. The tools below read it through a ``ctx: Context``
parameter, which the SDK keeps out of the tool's input schema entirely, so it is not something
the model can see or forge.

Named as a constant for the reason :data:`ASK_TOOL` is. ``hera_tools`` carries an opaque mapping
and does not read it; the *application* is what fills it in, so the string is written here and
travels rather than being agreed on by two packages that may not import each other. Namespaced,
because the mapping goes to every server including somebody else's.
"""

TOOL_NAMES = (
    "emotion",
    "ask",
    "remember",
    "note",
    "skill",
    "search",
    "scratch_write",
    "scratch_read",
    "scratch_list",
    "artifact_create",
    "artifact_edit",
    "artifact_read",
    "forget",
)
"""What this server offers, in the order they were added. Qualified, that is ``hera__emotion``
and its siblings — the ones a catalogue reports for the ``hera`` server, which is the question
a settings screen showing "5 tools" leaves a person asking."""

ARTIFACT_META = "artifact"
"""The key her artifact tools put their structured answer under (ADR 13).

``artifact_create`` returns text for the model *and* ``structured_content`` for the interface,
which is what lets a card be drawn without a new event variant: ``ToolResultEvent.structured`` is
already ``Any`` and already persisted. Named here for the reason :data:`ASK_TOOL` is — the browser
reads this key, and a string agreed on in two places is one that can disagree.
"""

SCRATCH_LISTING_LIMIT = 100
"""How many files one ``scratch_list`` reports. A ceiling for the same reason
:data:`SEARCH_LIMIT` is one: a listing longer than this is not an answer, it is the context
window spent on filenames."""

SEARCH_LIMIT = 20
"""The most results one call may ask for. A ceiling rather than a preference: a model that asks
for a hundred gets a page of snippets where the answer used to be, and pays for it twice --
once in the context window and once in how hard its own answer is to find afterwards."""


def build_builtin_server(
    *,
    memories: Memories | None = None,
    notes: NoteWriter | None = None,
    skills: SkillLibrary | None = None,
    searcher: Searcher | None = None,
    scratchpad: Scratchpad | None = None,
    artifacts: Artifacts | None = None,
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

    # The one tool on this server that is *not* run. `hera_chats` recognises it before dispatch,
    # records the question, and closes the turn the way a permission card closes it -- so the
    # answer that comes back is a person's words, and this body is only reached when something
    # calls it outside a turn.
    @server.tool(
        name=ASK_TOOL,
        title="Ask the person a question",
        description=(
            "Ask the person something and wait for their answer. This stops your turn: they "
            "see your question, type a reply, and you continue with it. Use it when being "
            "wrong would cost them real work -- a fact only they have, two readings of the "
            "request that lead somewhere genuinely different, or something hard to undo. Do "
            "not use it to be reassured, to ask what you could look up, or to check in; and "
            "ask one question rather than a list. If you can sensibly choose and say what you "
            "chose, do that instead."
        ),
    )
    async def ask(question: str, kind: str = "unsure") -> str:
        # Reached only when this server is driven directly -- over the transport v0.3 exposes,
        # or by a test. Inside a turn the question never gets here. Saying so plainly beats
        # returning something that looks like an answer nobody gave.
        raise ToolError(
            "this question was not put to anybody: `ask` suspends a turn so a person can "
            "reply, and nothing here is running one"
        )

    @server.tool(
        name="remember",
        title="Remember a fact",
        description=(
            "Write something down so it is in front of you in every conversation from now on: "
            "a preference, a decision, a fact about the person or their work — what you would "
            "want to know next week. `key` is its name and its identity, in the shape "
            "`prefers-short-answers`; writing the same key again replaces what is there, which "
            "is how you correct yourself. `description` is one line, for the list they read. "
            "Use `scope='chat'` for something that only holds in this conversation. Everything "
            "you have remembered is already in your prompt, so there is nothing to search and "
            "no reason to store what is in the conversation you can see. The space is limited: "
            "if there is none left you will be told what is taking it, and nothing is thrown "
            "away to make room."
        ),
    )
    async def remember(
        key: str,
        text: str,
        description: str,
        ctx: Context,
        why: str = "",
        scope: Literal["global", "chat"] = "global",
    ) -> str:
        if memories is None:
            raise ToolError("memory is not available in this deployment")
        # Only asked for when it is needed. A global memory is the ordinary case and has no
        # business failing because this server happens to be driven outside a turn.
        chat_id = _chat_of(ctx, "a memory kept for one conversation") if scope == "chat" else ""
        with _readable("remember that"):
            return await memories.remember(
                key.strip(),
                text,
                description=description,
                why=why,
                scope=scope,
                chat_id=chat_id,
            )

    @server.tool(
        name="forget",
        title="Stop carrying a memory",
        description=(
            "Stop carrying one of your memories, freeing the space it took. **The file is "
            "kept** and a person can switch it back on — this is not a delete, and you cannot "
            "delete one. Use it when something you wrote down has stopped being true, or after "
            "folding two memories into one to make room."
        ),
    )
    async def forget(key: str) -> str:
        if memories is None:
            raise ToolError("memory is not available in this deployment")
        with _readable("forget that"):
            return await memories.forget(key.strip())

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

    # The scratchpad, ADR 12. Three tools rather than two: folding the listing into `read` with
    # an empty name would be one fewer description at the cost of a conditional in prose, and
    # this project has already made that trade the other way once -- `ask` is a separate tool
    # from `emotion` for exactly this reason.
    #
    # None of them says "scratchpad" without saying what it is *for*. A model given a place to
    # write and no account of when to use it either never writes or writes everything down.

    @server.tool(
        name="scratch_write",
        title="Write to your scratchpad",
        description=(
            "Write a file to your scratchpad for this conversation -- a plan, a set of findings "
            "so far, a draft you are still working on. It is yours, not something the person "
            "reads, and it survives into later turns of this conversation, so use it for what "
            "you would otherwise have to re-derive or re-read the whole chat to recover. Prefer "
            "it to a very long answer whose real purpose is to remember something. `name` is a "
            "plain filename such as `plan.md`. `append=true` adds to the end instead of "
            "replacing. For a document the person keeps, use `note`; for a lasting fact about "
            "them, use `remember`."
        ),
    )
    async def scratch_write(name: str, text: str, ctx: Context, append: bool = False) -> str:
        if scratchpad is None:
            raise ToolError("a scratchpad is not available in this deployment")
        with _readable("write to the scratchpad"):
            return await scratchpad.write(_chat_of(ctx), name.strip(), text, append=append)

    @server.tool(
        name="scratch_read",
        title="Read from your scratchpad",
        description=(
            "Read back a file you wrote to your scratchpad in this conversation. Use it at the "
            "start of a turn when you left yourself something and need it in front of you "
            "again. `scratch_list` says what is there."
        ),
    )
    async def scratch_read(name: str, ctx: Context) -> str:
        if scratchpad is None:
            raise ToolError("a scratchpad is not available in this deployment")
        with _readable("read the scratchpad"):
            body = await scratchpad.read(_chat_of(ctx), name.strip())
        if body is None:
            raise ToolError(f"no file named {name!r} in this conversation's scratchpad")
        return body

    @server.tool(
        name="scratch_list",
        title="List your scratchpad",
        description=(
            "List what you have written to your scratchpad in this conversation, with sizes. "
            "Cheap; call it when you are unsure whether you left yourself anything."
        ),
    )
    async def scratch_list(ctx: Context) -> str:
        if scratchpad is None:
            raise ToolError("a scratchpad is not available in this deployment")
        with _readable("list the scratchpad"):
            found = await scratchpad.files(_chat_of(ctx))
        if not found:
            # Not a ToolError: an empty scratchpad is the ordinary state of a new conversation,
            # and telling her it *failed* is how a tool stops being used. Same reasoning as
            # "no results" in `search`.
            return "your scratchpad for this conversation is empty"
        listed = sorted(found, key=lambda file: file.name)[:SCRATCH_LISTING_LIMIT]
        lines = [f"{file.name} ({file.size} bytes)" for file in listed]
        if len(found) > len(listed):
            lines.append(f"… and {len(found) - len(listed)} more")
        return "\n".join(lines)

    # Artifacts, ADR 13. The other side of the scratchpad: that one is hers and nobody reads it,
    # these are what she publishes. Three tools, and each of them is load-bearing -- drop `read`
    # and `edit` cannot be used, drop `edit` and every change is a full rewrite, drop `create`
    # and there is nothing to edit.
    #
    # There is no `artifact_list`. What is in the directory is on the screen already, and a tool
    # that read her own filenames back into the context window would spend it on something she
    # can see.

    @server.tool(
        name="artifact_create",
        title="Publish an artifact",
        description=(
            "Publish a file the person can open: a page, a document, a diagram, a small program. "
            "This is the thing you were asked for, and it appears beside your answer with its "
            "name on it, ready to read and download -- so put the work here rather than into a "
            "very long answer, and then say what you made in a sentence or two. `name` is a "
            "plain filename and its extension decides how it is drawn: `.html` renders as a "
            "page, `.svg` draws, `.md` is typeset, anything else is shown as code. Publishing "
            "the same name again replaces what was there, so use `artifact_edit` for a change. "
            "Set `inline=true` for a figure that belongs in the middle of what you are saying -- "
            "a diagram or a chart explaining the paragraph above it -- and leave it false for a "
            "page or a document, which the person opens beside the conversation. For working "
            "notes only you read, use `scratch_write` instead."
        ),
    )
    async def artifact_create(
        name: str, content: str, ctx: Context, inline: bool = False
    ) -> CallToolResult:
        if artifacts is None:
            raise ToolError("publishing is not available in this deployment")
        cleaned = name.strip()
        with _readable("publish that"):
            written = await artifacts.create(_chat_of(ctx, "an artifact"), cleaned, content)
        # Text for the model, structured content for the interface, in one result. The card is
        # drawn from the second (ADR 13) and needs no event variant of its own: this is typed
        # JSON the *server* produced, not something read back out of what a model wrote.
        return CallToolResult(
            content=[TextContent(type="text", text=f"published {cleaned} ({written} bytes)")],
            structured_content={
                ARTIFACT_META: {"name": cleaned, "inline": inline, "bytes": written}
            },
        )

    @server.tool(
        name="artifact_edit",
        title="Change part of an artifact",
        description=(
            "Change one passage of an artifact you have already published, without writing the "
            "whole thing out again. `find` is the exact text to replace and it must appear "
            "**exactly once** -- include enough of the surrounding lines to be certain of that "
            "-- and `replace` is what goes in its place. Prefer this to publishing the file "
            "again whenever the change is smaller than the file: re-emitting a long page takes "
            "minutes and risks losing more than it fixes. If you no longer have the current "
            "content in front of you, read it back with `artifact_read` first."
        ),
    )
    async def artifact_edit(name: str, find: str, replace: str, ctx: Context) -> str:
        if artifacts is None:
            raise ToolError("publishing is not available in this deployment")
        cleaned = name.strip()
        with _readable(f"edit {cleaned}"):
            written = await artifacts.edit(_chat_of(ctx, "an artifact"), cleaned, find, replace)
        # No structured content, and that is the decision rather than an omission: an artifact has
        # one current state everywhere it appears, so the card made when it was published already
        # shows this change. A second card would draw the same file twice.
        return f"edited {cleaned} ({written} bytes)"

    @server.tool(
        name="artifact_read",
        title="Read an artifact back",
        description=(
            "Read back an artifact you published in this conversation. Its content is not in the "
            "conversation -- only the card is -- so call this in a later turn when you need the "
            "current text, in particular before `artifact_edit`, to build a `find` out of "
            "something that is really in the file."
        ),
    )
    async def artifact_read(name: str, ctx: Context) -> str:
        if artifacts is None:
            raise ToolError("publishing is not available in this deployment")
        cleaned = name.strip()
        with _readable(f"read {cleaned}"):
            body = await artifacts.read(_chat_of(ctx, "an artifact"), cleaned)
        if body is None:
            raise ToolError(f"nothing named {name!r} has been published in this conversation")
        return body

    return server


@contextmanager
def _readable(what: str) -> Iterator[None]:
    """Let whatever the adapter said reach the model, instead of the SDK's generic sentence.

    Without this the SDK replaces any exception that is not a ``ToolError`` with "Error
    executing tool scratch_write", which tells her nothing to act on — and the adapter's
    refusals are the ones most worth reading: *that is not a plain filename*, *that would put
    it over the size limit*. Both have an obvious next move and neither survives being
    generalised.

    Broad on purpose, and it hides nothing: a ``ToolError`` already carries its own message and
    passes through untouched.
    """
    try:
        yield
    except ToolError:
        raise
    except Exception as cause:
        raise ToolError(f"could not {what}: {cause}") from cause


def _chat_of(ctx: Context, what: str = "the scratchpad") -> str:
    """Which conversation this call is part of, from the request's ``_meta`` (ADR 12).

    Reached only by the tools that are meaningless outside one. Missing means this server is
    being driven directly -- over the transport v0.3 exposes, or by a test -- and saying so
    plainly beats inventing a directory and writing into it, which nobody would find.

    ``what`` is in the sentence rather than fixed, because two different things now belong to a
    conversation and *the scratchpad is not part of one* is a confusing thing to be told after
    asking to publish a page.
    """
    meta = getattr(ctx.request_context, "meta", None) or {}
    chat_id = meta.get(CHAT_ID_META)
    if not isinstance(chat_id, str) or not chat_id:
        raise ToolError(f"{what} belongs to a conversation, and this call is not part of one")
    return chat_id


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

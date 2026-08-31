"""Her own tools, exercised the way the model reaches them.

Through a real client over the protocol, so the schema, the description and the ``is_error``
convention are all part of what is asserted. That her tools are namespaced and permission
checked like anybody else's (ADR 4) is `hera_tools`' claim to prove, and it does.
"""

from __future__ import annotations

import pytest
from mcp.server.mcpserver import MCPServer
from mcp_support import (
    AngryScratchpad,
    FakeArtifacts,
    FakeMemories,
    FakeNotes,
    FakeScratchpad,
    FakeSearch,
    FakeSkills,
    in_chat,
    said,
    talking_to,
)

from hera_mcp import (
    ARTIFACT_META,
    BUILTIN_SERVER_NAME,
    SCRATCH_LISTING_LIMIT,
    SEARCH_LIMIT,
    TOOL_NAMES,
    build_builtin_server,
)


async def test_it_offers_her_whole_catalogue_under_her_name(wired: MCPServer) -> None:
    """What a settings screen counts for the ``hera`` server."""
    async with talking_to(wired) as client:
        listing = await client.list_tools()

    assert sorted(tool.name for tool in listing.tools) == sorted(TOOL_NAMES)
    assert build_builtin_server().name == BUILTIN_SERVER_NAME


class TestEmotion:
    async def test_it_acknowledges_and_nothing_more(self, wired: MCPServer) -> None:
        """The call itself is the record; the answer only has to let generation continue."""
        async with talking_to(wired) as client:
            result = await client.call_tool("emotion", {"kind": "doubt", "text": "hm"})

        assert not result.is_error
        assert said(result) == "shown"

    async def test_an_invented_kind_is_accepted(self, wired: MCPServer) -> None:
        """ADR 3: ``kind`` is free text and unknown kinds render generically."""
        async with talking_to(wired) as client:
            result = await client.call_tool("emotion", {"kind": "wistful"})

        assert not result.is_error

    async def test_the_description_says_a_kind_may_be_invented(self, wired: MCPServer) -> None:
        """A model that hard-obeys its schema needs the freedom written where it can see it."""
        async with talking_to(wired) as client:
            listing = await client.list_tools()

        emotion = next(tool for tool in listing.tools if tool.name == "emotion")
        assert emotion.description is not None
        assert "invent" in emotion.description

    async def test_a_missing_kind_comes_back_as_a_tool_error(self, wired: MCPServer) -> None:
        """Schema validation happens in the server, and arrives as a result, not a crash."""
        async with talking_to(wired) as client:
            result = await client.call_tool("emotion", {"text": "no kind"})

        assert result.is_error


class TestRemember:
    async def test_it_writes_through_the_port(
        self, wired: MCPServer, memories: FakeMemories
    ) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "remember",
                {
                    "key": "prefers-dark-roast",
                    "text": "They drink it black.",
                    "description": "Coffee",
                },
            )

        assert not result.is_error
        assert memories.written == {
            "prefers-dark-roast": ("They drink it black.", "Coffee", "global", "")
        }

    async def test_the_input_schema_is_what_the_model_may_fill_in(self, wired: MCPServer) -> None:
        """No ``chat_id`` — a memory scoped to a conversation learns which one from ``_meta``
        (ADR 12), and a field in the schema is a field the model would invent. The ``ctx``
        parameter that carries it is kept out by the SDK, which is somebody else's behaviour
        and therefore worth a test rather than a comment."""
        async with talking_to(wired) as client:
            listing = await client.list_tools()

        remember = next(tool for tool in listing.tools if tool.name == "remember")
        assert sorted(remember.input_schema.get("properties", {})) == [
            "description",
            "key",
            "scope",
            "text",
            "why",
        ]
        assert sorted(remember.input_schema.get("required", [])) == ["description", "key", "text"]

    async def test_the_scope_defaults_to_global(
        self, wired: MCPServer, memories: FakeMemories
    ) -> None:
        async with talking_to(wired) as client:
            await client.call_tool("remember", {"key": "k", "text": "x", "description": "d"})

        assert memories.written["k"][2] == "global"

    async def test_a_chat_memory_learns_its_chat_from_meta(
        self, wired: MCPServer, memories: FakeMemories
    ) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "remember",
                {"key": "k", "text": "x", "description": "d", "scope": "chat"},
                meta=in_chat("chat-7"),
            )

        assert not result.is_error
        assert memories.written["k"][3] == "chat-7"

    async def test_a_chat_memory_outside_a_conversation_says_so(
        self, wired: MCPServer, memories: FakeMemories
    ) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "remember", {"key": "k", "text": "x", "description": "d", "scope": "chat"}
            )

        assert result.is_error
        assert "not part of one" in said(result)
        assert memories.written == {}

    async def test_a_global_memory_does_not_need_a_conversation(
        self, wired: MCPServer, memories: FakeMemories
    ) -> None:
        """The ordinary case has no business failing because this server happened to be driven
        outside a turn."""
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "remember", {"key": "k", "text": "x", "description": ""}
            )

        assert not result.is_error

    async def test_a_scope_the_schema_does_not_allow_is_refused(
        self, wired: MCPServer, memories: FakeMemories
    ) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "remember", {"key": "k", "text": "x", "description": "d", "scope": "planet"}
            )

        assert result.is_error
        assert memories.written == {}

    async def test_a_full_store_reaches_the_model_as_something_it_can_act_on(
        self, wired_full: MCPServer
    ) -> None:
        """The adapter's refusal, not the SDK's "Error executing tool remember" — that sentence
        tells her nothing, and this one tells her exactly what to do next."""
        async with talking_to(wired_full) as client:
            result = await client.call_tool(
                "remember", {"key": "k", "text": "x", "description": ""}
            )

        assert result.is_error
        assert "fold two of these into one" in said(result)


class TestForget:
    async def test_it_switches_one_off_through_the_port(
        self, wired: MCPServer, memories: FakeMemories
    ) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool("forget", {"key": "prefers-dark-roast"})

        assert not result.is_error
        assert memories.forgotten == ["prefers-dark-roast"]

    async def test_the_description_says_the_file_is_kept(self, wired: MCPServer) -> None:
        """It is called ``forget`` because that is the word the model reaches for, so the
        description is the only thing stopping it meaning what the model would assume."""
        async with talking_to(wired) as client:
            listing = await client.list_tools()

        forget = next(tool for tool in listing.tools if tool.name == "forget")
        assert forget.description is not None
        assert "file is" in forget.description and "kept" in forget.description
        assert "cannot delete" in forget.description


class TestNote:
    async def test_it_writes_through_the_port(self, wired: MCPServer, notes: FakeNotes) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool("note", {"text": "the plan", "title": "Plan"})

        assert not result.is_error
        assert notes.written == [("Plan", "the plan")]


class TestSkill:
    async def test_it_returns_the_body(self, wired: MCPServer, skills: FakeSkills) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool("skill", {"name": "writing"})

        assert not result.is_error
        assert said(result) == skills.bodies["writing"]

    async def test_an_unknown_skill_says_what_there_is(self, wired: MCPServer) -> None:
        """Told what exists, a model asks again correctly instead of giving up."""
        async with talking_to(wired) as client:
            result = await client.call_tool("skill", {"name": "cooking"})

        assert result.is_error
        assert "writing" in said(result)


class TestSearch:
    """The one tool of hers that leaves the machine."""

    async def test_it_asks_the_engine_and_reads_back_what_came(
        self, wired: MCPServer, searcher: FakeSearch
    ) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool("search", {"query": "kerberos tgt", "limit": 2})

        assert not result.is_error
        assert searcher.asked == [("kerberos tgt", 2)]
        text = said(result)
        # Numbered, because she refers back to them, and every link on its own line so it
        # survives being copied out of an answer.
        assert "1. Kerberos" in text
        assert "https://example.test/kerberos" in text
        assert "2. TGT" in text

    async def test_finding_nothing_is_an_answer_and_not_a_failure(self) -> None:
        """A model told the search is broken stops searching. Told nothing was found, it tries
        other words -- which is the behaviour worth having, so the two must not look alike."""
        server = build_builtin_server(searcher=FakeSearch())
        async with talking_to(server) as client:
            result = await client.call_tool("search", {"query": "asdkjhqwlekjh"})

        assert not result.is_error
        assert "no results" in said(result)

    async def test_an_engine_that_failed_says_why(self) -> None:
        """Not the SDK's "Error executing tool search": rate-limited and unreachable want
        different next moves, and she can only pick one if the reason survives."""
        server = build_builtin_server(searcher=FakeSearch(fails=RuntimeError("429 slow down")))
        async with talking_to(server) as client:
            result = await client.call_tool("search", {"query": "kerberos"})

        assert result.is_error
        assert "429 slow down" in said(result)

    async def test_an_empty_query_is_refused_before_anything_leaves(
        self, wired: MCPServer, searcher: FakeSearch
    ) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool("search", {"query": "   "})

        assert result.is_error
        assert searcher.asked == [], "nothing was sent anywhere"

    async def test_the_limit_is_capped(self, wired: MCPServer, searcher: FakeSearch) -> None:
        """A hundred snippets is a page of noise where the answer used to be, and it is paid
        for twice -- in the window, and in how hard her own answer is to find afterwards."""
        async with talking_to(wired) as client:
            await client.call_tool("search", {"query": "x", "limit": 500})
            await client.call_tool("search", {"query": "x", "limit": 0})

        assert [limit for _, limit in searcher.asked] == [SEARCH_LIMIT, 1]

    async def test_the_description_tells_her_to_prefer_it_to_guessing(
        self, wired: MCPServer
    ) -> None:
        """The whole reason this tool exists: a model with no way to look something up does not
        say it cannot check, it guesses fluently. That has to be written where it can see it."""
        async with talking_to(wired) as client:
            listing = await client.list_tools()

        search = next(tool for tool in listing.tools if tool.name == "search")
        assert search.description is not None
        assert "guessing" in search.description


class TestUnwiredPorts:
    """A deployment with no memories still has to be usable, and honest about why.

    ``note`` waits for somewhere to put a document; a deployment can also be built with no
    memory, no scratchpad and no search, and every one of them is listed anyway.
    """

    async def test_the_tools_are_still_listed(self, bare: MCPServer) -> None:
        """A model that cannot see ``remember`` concludes it cannot remember, and says so."""
        async with talking_to(bare) as client:
            listing = await client.list_tools()

        assert sorted(tool.name for tool in listing.tools) == sorted(TOOL_NAMES)

    @pytest.mark.parametrize(
        ("tool", "arguments"),
        [
            ("remember", {"key": "k", "text": "x", "description": "d"}),
            ("forget", {"key": "k"}),
            ("note", {"text": "x"}),
            ("skill", {"name": "writing"}),
            ("search", {"query": "kerberos"}),
            ("scratch_write", {"name": "plan.md", "text": "x"}),
            ("scratch_read", {"name": "plan.md"}),
            ("scratch_list", {}),
            ("artifact_create", {"name": "page.html", "content": "<p>x</p>"}),
            ("artifact_edit", {"name": "page.html", "find": "x", "replace": "y"}),
            ("artifact_read", {"name": "page.html"}),
        ],
    )
    async def test_they_answer_that_they_are_unavailable(
        self, bare: MCPServer, tool: str, arguments: dict[str, str]
    ) -> None:
        async with talking_to(bare) as client:
            result = await client.call_tool(tool, arguments)

        assert result.is_error
        assert "not available" in said(result)

    async def test_emotion_needs_nothing_wired(self, bare: MCPServer) -> None:
        async with talking_to(bare) as client:
            result = await client.call_tool("emotion", {"kind": "hope"})

        assert not result.is_error


class TestTheScratchpad:
    """ADR 12. Three tools, and the interesting part is not any of them individually — it is
    that a call knows which conversation it belongs to without the model being able to say."""

    async def test_a_write_goes_to_the_chat_the_call_names(
        self, wired: MCPServer, scratchpad: FakeScratchpad
    ) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "scratch_write", {"name": "plan.md", "text": "1. read it"}, meta=in_chat("c-1")
            )

        assert not result.is_error
        assert scratchpad.chats == {"c-1": {"plan.md": "1. read it"}}

    async def test_two_conversations_do_not_share_one(
        self, wired: MCPServer, scratchpad: FakeScratchpad
    ) -> None:
        """The whole point of the ``_meta`` mechanism, stated as a test: a scratchpad that
        ignored the id would pass every other assertion in this class."""
        async with talking_to(wired) as client:
            await client.call_tool(
                "scratch_write", {"name": "plan.md", "text": "mine"}, meta=in_chat("c-1")
            )
            result = await client.call_tool(
                "scratch_read", {"name": "plan.md"}, meta=in_chat("c-2")
            )

        assert result.is_error
        assert "no file named" in said(result)

    async def test_the_chat_id_is_not_in_the_schema(self, wired: MCPServer) -> None:
        """A ``Context`` parameter is excluded by the SDK, which is what makes this safe: a
        field in the schema is a field the model can see and will fill in with a guess."""
        async with talking_to(wired) as client:
            listing = await client.list_tools()

        for name in ("scratch_write", "scratch_read", "scratch_list"):
            tool = next(t for t in listing.tools if t.name == name)
            properties = tool.input_schema.get("properties", {})
            assert "ctx" not in properties
            assert not any("chat" in key.lower() for key in properties)

    async def test_a_call_outside_a_conversation_says_so(self, wired: MCPServer) -> None:
        """Reached over the transport v0.3 exposes, or by a script. Refusing beats inventing a
        directory and writing into one nobody would find."""
        async with talking_to(wired) as client:
            result = await client.call_tool("scratch_write", {"name": "plan.md", "text": "x"})

        assert result.is_error
        assert "not part of one" in said(result)

    async def test_appending_adds_rather_than_replaces(
        self, wired: MCPServer, scratchpad: FakeScratchpad
    ) -> None:
        async with talking_to(wired) as client:
            await client.call_tool(
                "scratch_write", {"name": "log.md", "text": "one\n"}, meta=in_chat("c-1")
            )
            await client.call_tool(
                "scratch_write",
                {"name": "log.md", "text": "two\n", "append": True},
                meta=in_chat("c-1"),
            )

        assert scratchpad.chats["c-1"]["log.md"] == "one\ntwo\n"

    async def test_reading_back_what_was_written(self, wired: MCPServer) -> None:
        async with talking_to(wired) as client:
            await client.call_tool(
                "scratch_write", {"name": "plan.md", "text": "1. read it"}, meta=in_chat("c-1")
            )
            result = await client.call_tool(
                "scratch_read", {"name": "plan.md"}, meta=in_chat("c-1")
            )

        assert not result.is_error
        assert said(result) == "1. read it"

    async def test_a_missing_file_is_a_failed_result_naming_it(self, wired: MCPServer) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "scratch_read", {"name": "gone.md"}, meta=in_chat("c-1")
            )

        assert result.is_error
        assert "gone.md" in said(result)

    async def test_an_empty_scratchpad_is_not_an_error(self, wired: MCPServer) -> None:
        """Same reasoning as ``search`` returning nothing: a model told the tool is broken stops
        using it, and a model told there is nothing there writes something."""
        async with talking_to(wired) as client:
            result = await client.call_tool("scratch_list", {}, meta=in_chat("c-1"))

        assert not result.is_error
        assert "empty" in said(result)

    async def test_a_listing_names_each_file_with_its_size(self, wired: MCPServer) -> None:
        async with talking_to(wired) as client:
            await client.call_tool(
                "scratch_write", {"name": "plan.md", "text": "abcd"}, meta=in_chat("c-1")
            )
            result = await client.call_tool("scratch_list", {}, meta=in_chat("c-1"))

        assert said(result) == "plan.md (4 bytes)"

    async def test_a_long_listing_is_capped_and_says_so(
        self, wired: MCPServer, scratchpad: FakeScratchpad
    ) -> None:
        """A ceiling for the reason ``SEARCH_LIMIT`` is one: past a point a listing is not an
        answer, it is the context window spent on filenames."""
        extra = 5
        scratchpad.chats["c-1"] = {
            f"note-{index:03}.md": "x" for index in range(SCRATCH_LISTING_LIMIT + extra)
        }
        async with talking_to(wired) as client:
            result = await client.call_tool("scratch_list", {}, meta=in_chat("c-1"))

        lines = said(result).splitlines()
        assert len(lines) == SCRATCH_LISTING_LIMIT + 1
        assert lines[-1] == f"… and {extra} more"

    async def test_an_adapters_refusal_reaches_the_model(self, scratchpad: FakeScratchpad) -> None:
        """Without the wrapping, the SDK replaces this with "Error executing tool
        scratch_write" — and the refusals worth reading are exactly the ones with a next move
        in them: *that is not a plain filename*, *that is over the size limit*."""
        angry = build_builtin_server(scratchpad=AngryScratchpad())
        async with talking_to(angry) as client:
            result = await client.call_tool(
                "scratch_write", {"name": "../x", "text": "x"}, meta=in_chat("c-1")
            )

        assert result.is_error
        assert "not a plain filename" in said(result)

    async def test_the_three_descriptions_say_what_it_is_for(self, wired: MCPServer) -> None:
        """Tool descriptions are prompt text. A place to write with no account of when to use
        it produces a model that either never writes or writes everything down."""
        async with talking_to(wired) as client:
            listing = await client.list_tools()

        write = next(t for t in listing.tools if t.name == "scratch_write")
        assert write.description is not None
        # It has to be told what the *other* two tools are for, or the three overlap and the
        # choice between them becomes arbitrary.
        assert "note" in write.description
        assert "remember" in write.description


class TestArtifacts:
    """ADR 13. Three tools over one directory, and the card is drawn from what `create`
    returns rather than from a new event variant."""

    async def test_a_create_publishes_into_the_chat_the_call_names(
        self, wired: MCPServer, artifacts: FakeArtifacts
    ) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "artifact_create",
                {"name": "page.html", "content": "<h1>Hi</h1>"},
                meta=in_chat("c-1"),
            )

        assert not result.is_error
        assert artifacts.chats == {"c-1": {"page.html": "<h1>Hi</h1>"}}

    async def test_it_answers_with_text_for_her_and_structure_for_the_card(
        self, wired: MCPServer
    ) -> None:
        """The mechanism the whole feature rests on, and it is the SDK's behaviour rather than
        ours: one result carries the sentence the model reads *and* the JSON the interface draws
        a card from, so ``ToolResultEvent.structured`` needs no new event variant (ADR 13)."""
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "artifact_create",
                {"name": "flow.svg", "content": "<svg/>", "inline": True},
                meta=in_chat("c-1"),
            )

        assert said(result) == "published flow.svg (6 bytes)"
        assert result.structured_content == {
            ARTIFACT_META: {"name": "flow.svg", "inline": True, "bytes": 6}
        }

    async def test_inline_defaults_to_a_card_rather_than_to_the_flow(
        self, wired: MCPServer
    ) -> None:
        """A page drawn in the middle of an answer is the wrong default: it is the larger of the
        two things and the one a person goes and opens."""
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "artifact_create", {"name": "report.md", "content": "# Report"}, meta=in_chat("c-1")
            )

        assert result.structured_content is not None
        assert result.structured_content[ARTIFACT_META]["inline"] is False

    async def test_two_conversations_do_not_share_them(
        self, wired: MCPServer, artifacts: FakeArtifacts
    ) -> None:
        async with talking_to(wired) as client:
            await client.call_tool(
                "artifact_create", {"name": "page.html", "content": "mine"}, meta=in_chat("c-1")
            )
            result = await client.call_tool(
                "artifact_read", {"name": "page.html"}, meta=in_chat("c-2")
            )

        assert result.is_error
        assert "page.html" in said(result)

    async def test_the_chat_id_is_not_in_any_of_the_schemas(self, wired: MCPServer) -> None:
        """The same assertion the scratchpad earned, for the same reason: a ``Context``
        parameter is excluded by the SDK, and a field in the schema is one the model can see and
        will fill in with a guess."""
        async with talking_to(wired) as client:
            listing = await client.list_tools()

        create = next(t for t in listing.tools if t.name == "artifact_create")
        assert sorted(create.input_schema.get("properties", {})) == ["content", "inline", "name"]
        for name in ("artifact_create", "artifact_edit", "artifact_read"):
            tool = next(t for t in listing.tools if t.name == name)
            properties = tool.input_schema.get("properties", {})
            assert "ctx" not in properties
            assert not any("chat" in key.lower() for key in properties)

    async def test_a_call_outside_a_conversation_says_which_thing_it_meant(
        self, wired: MCPServer
    ) -> None:
        """*The scratchpad is not part of a conversation* is a confusing thing to be told after
        asking to publish a page, so the sentence names what was asked for."""
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "artifact_create", {"name": "page.html", "content": "x"}
            )

        assert result.is_error
        assert "an artifact belongs to a conversation" in said(result)

    async def test_an_edit_changes_the_passage_and_nothing_else(
        self, wired: MCPServer, artifacts: FakeArtifacts
    ) -> None:
        """The point of the tool: re-emitting a long page to change one colour is minutes of
        generation, and it is what has actually been failing against the target endpoint."""
        artifacts.chats["c-1"] = {"page.html": "<body bg='red'>a long page</body>"}
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "artifact_edit",
                {"name": "page.html", "find": "red", "replace": "brass"},
                meta=in_chat("c-1"),
            )

        assert not result.is_error
        assert artifacts.chats["c-1"]["page.html"] == "<body bg='brass'>a long page</body>"

    async def test_an_edit_draws_no_second_card(self, wired: MCPServer) -> None:
        """An artifact has one current state everywhere it appears, so the card made when it was
        published already shows this change (ADR 13). A second card would draw one file twice."""
        async with talking_to(wired) as client:
            await client.call_tool(
                "artifact_create", {"name": "page.html", "content": "red"}, meta=in_chat("c-1")
            )
            result = await client.call_tool(
                "artifact_edit",
                {"name": "page.html", "find": "red", "replace": "brass"},
                meta=in_chat("c-1"),
            )

        # The SDK derives `{"result": …}` for any tool that returns a plain string, so what the
        # interface keys on is the *presence of the artifact key* rather than structure at all.
        assert result.structured_content == {"result": "edited page.html (5 bytes)"}
        assert ARTIFACT_META not in (result.structured_content or {})

    async def test_an_ambiguous_find_is_refused_in_words_she_can_act_on(
        self, wired: MCPServer, artifacts: FakeArtifacts
    ) -> None:
        """Zero and several are both refusals, because a replacement that hit the wrong one of
        three is a silent corruption and she cannot see the file to notice."""
        artifacts.chats["c-1"] = {"page.html": "red red red"}
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "artifact_edit",
                {"name": "page.html", "find": "red", "replace": "brass"},
                meta=in_chat("c-1"),
            )

        assert result.is_error
        assert "matches 3 times" in said(result)

    async def test_reading_something_that_was_never_published_says_so(
        self, wired: MCPServer
    ) -> None:
        async with talking_to(wired) as client:
            result = await client.call_tool(
                "artifact_read", {"name": "gone.md"}, meta=in_chat("c-1")
            )

        assert result.is_error
        assert "gone.md" in said(result)

    async def test_reading_gives_back_the_current_content(self, wired: MCPServer) -> None:
        """``read`` exists because ``edit`` is useless without it: in a later turn the content is
        not in the conversation, only the card is, so there is nothing to build a `find` from."""
        async with talking_to(wired) as client:
            await client.call_tool(
                "artifact_create", {"name": "report.md", "content": "# Report"}, meta=in_chat("c-1")
            )
            result = await client.call_tool(
                "artifact_read", {"name": "report.md"}, meta=in_chat("c-1")
            )

        assert said(result) == "# Report"

    async def test_the_descriptions_separate_it_from_the_scratchpad(self, wired: MCPServer) -> None:
        """Tool descriptions are prompt text, and these two tools write a file each. A model
        choosing between two overlapping descriptions chooses at random, so `create` has to say
        which one is the deliverable and which one is hers."""
        async with talking_to(wired) as client:
            listing = await client.list_tools()

        create = next(t for t in listing.tools if t.name == "artifact_create")
        assert create.description is not None
        assert "scratch_write" in create.description
        # The extension is the kind (ADR 13), so the model has to be told that its choice of
        # filename is a choice about how the thing is drawn.
        assert ".svg" in create.description
        assert "inline" in create.description

        edit = next(t for t in listing.tools if t.name == "artifact_edit")
        assert edit.description is not None
        assert "exactly once" in edit.description
        assert "artifact_read" in edit.description

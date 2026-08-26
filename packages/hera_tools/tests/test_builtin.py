"""Hera's own tools, exercised the way the model reaches them.

Everything here goes through the registry: a real MCP server, a real client, a real permission
check. If these could be tested by calling the Python functions directly, the ADR-4 claim that
her tools are "not a special case" would not be true.
"""

from __future__ import annotations

import pytest
from conftest import FakeMemories, FakeNotes, FakeSkills
from hera_tools.registry import ToolRegistry
from hera_tools.results import Failure, ToolInvocation

from hera_permissions import PermissionSet, Policy
from hera_tools import BUILTIN_SERVER_NAME, ManagedServer, ToolsSettings, build_builtin_server


async def test_her_tools_are_namespaced_like_everyone_else(registry: ToolRegistry) -> None:
    catalogue = await registry.catalogue()
    assert catalogue.names() == (
        "hera__emotion",
        "hera__note",
        "hera__remember",
        "hera__skill",
    )


async def test_the_server_is_called_hera(registry: ToolRegistry) -> None:
    catalogue = await registry.catalogue()
    assert {tool.server for tool in catalogue.tools} == {BUILTIN_SERVER_NAME}


class TestEmotion:
    async def test_it_acknowledges_and_nothing_more(self, registry: ToolRegistry) -> None:
        """The call itself is the record; the answer only has to let generation continue."""
        result = await registry.dispatch(
            ToolInvocation(
                call_id="c1", tool="hera__emotion", arguments={"kind": "doubt", "text": "hm"}
            )
        )
        assert result.ok
        assert result.text == "shown"

    async def test_an_invented_kind_is_accepted(self, registry: ToolRegistry) -> None:
        """ADR 3: ``kind`` is free text and unknown kinds render generically."""
        result = await registry.dispatch(
            ToolInvocation(call_id="c1", tool="hera__emotion", arguments={"kind": "wistful"})
        )
        assert result.ok

    async def test_the_description_says_a_kind_may_be_invented(
        self, registry: ToolRegistry
    ) -> None:
        """A model that hard-obeys its schema needs the freedom written where it can see it."""
        catalogue = await registry.catalogue()
        emotion = catalogue.get("hera__emotion")
        assert emotion is not None
        assert "invent" in emotion.description

    async def test_a_missing_kind_comes_back_as_a_tool_error(self, registry: ToolRegistry) -> None:
        """Schema validation happens in the server, and arrives as a result, not a crash."""
        result = await registry.dispatch(
            ToolInvocation(call_id="c1", tool="hera__emotion", arguments={"text": "no kind"})
        )
        assert not result.ok
        assert result.failure is Failure.TOOL_ERROR


class TestRemember:
    async def test_it_writes_through_the_port(
        self, registry: ToolRegistry, memories: FakeMemories
    ) -> None:
        result = await registry.dispatch(
            ToolInvocation(
                call_id="c1",
                tool="hera__remember",
                arguments={"text": "prefers dark roast", "scope": "global"},
            )
        )
        assert result.ok
        assert memories.written == [("prefers dark roast", "global")]

    async def test_the_scope_defaults_to_global(
        self, registry: ToolRegistry, memories: FakeMemories
    ) -> None:
        await registry.dispatch(
            ToolInvocation(call_id="c1", tool="hera__remember", arguments={"text": "x"})
        )
        assert memories.written == [("x", "global")]

    async def test_a_scope_the_schema_does_not_allow_is_refused(
        self, registry: ToolRegistry, memories: FakeMemories
    ) -> None:
        result = await registry.dispatch(
            ToolInvocation(
                call_id="c1", tool="hera__remember", arguments={"text": "x", "scope": "planet"}
            )
        )
        assert not result.ok
        assert memories.written == []


class TestNote:
    async def test_it_writes_through_the_port(
        self, registry: ToolRegistry, notes: FakeNotes
    ) -> None:
        result = await registry.dispatch(
            ToolInvocation(
                call_id="c1",
                tool="hera__note",
                arguments={"text": "the plan", "title": "Plan"},
            )
        )
        assert result.ok
        assert notes.written == [("Plan", "the plan")]


class TestSkill:
    async def test_it_returns_the_body(self, registry: ToolRegistry, skills: FakeSkills) -> None:
        result = await registry.dispatch(
            ToolInvocation(call_id="c1", tool="hera__skill", arguments={"name": "writing"})
        )
        assert result.ok
        assert result.text == skills.bodies["writing"]

    async def test_an_unknown_skill_says_what_there_is(self, registry: ToolRegistry) -> None:
        """Told what exists, a model asks again correctly instead of giving up."""
        result = await registry.dispatch(
            ToolInvocation(call_id="c1", tool="hera__skill", arguments={"name": "cooking"})
        )
        assert not result.ok
        assert "writing" in result.text


class TestUnwiredPorts:
    """A deployment with no memories still has to be usable, and honest about why."""

    @pytest.fixture
    async def bare(self, settings: ToolsSettings) -> ToolRegistry:
        return ToolRegistry(
            [ManagedServer.in_process("hera", build_builtin_server(), settings)],
            policy=Policy(base=PermissionSet.of(allow=["*"])),
        )

    async def test_the_tools_are_still_listed(self, bare: ToolRegistry) -> None:
        """A model that cannot see ``remember`` concludes it cannot remember, and says so."""
        assert "hera__remember" in await bare.catalogue()
        await bare.aclose()

    @pytest.mark.parametrize(
        ("tool", "arguments"),
        [
            ("hera__remember", {"text": "x"}),
            ("hera__note", {"text": "x"}),
            ("hera__skill", {"name": "writing"}),
        ],
    )
    async def test_they_answer_that_they_are_unavailable(
        self, bare: ToolRegistry, tool: str, arguments: dict[str, str]
    ) -> None:
        result = await bare.dispatch(ToolInvocation(call_id="c1", tool=tool, arguments=arguments))
        assert not result.ok
        assert "not available" in result.text
        await bare.aclose()

    async def test_emotion_needs_nothing_wired(self, bare: ToolRegistry) -> None:
        result = await bare.dispatch(
            ToolInvocation(call_id="c1", tool="hera__emotion", arguments={"kind": "hope"})
        )
        assert result.ok
        await bare.aclose()

"""Fixtures for her own server.

A real :class:`mcp.Client` over the SDK's in-memory transport, not a call to the Python
function underneath. What is worth testing here is the part the model actually meets: the
schema the SDK derived from the signature, the description it reads before deciding to call,
and the ``is_error`` convention a refusal comes back through. Calling ``emotion("doubt")``
directly would assert that our assumptions agree with themselves.

This package imports no ``hera_*`` package and its tests keep to that as well — mounting the
server in a `hera_tools` registry is that package's test, not this one's.
"""

from __future__ import annotations

import pytest
from mcp.server.mcpserver import MCPServer
from mcp_support import (
    FakeArtifacts,
    FakeMemories,
    FakeNotes,
    FakeScratchpad,
    FakeSearch,
    FakeSkills,
)

from hera_mcp import Hit, build_builtin_server


@pytest.fixture
def memories() -> FakeMemories:
    return FakeMemories()


@pytest.fixture
def notes() -> FakeNotes:
    return FakeNotes()


@pytest.fixture
def skills() -> FakeSkills:
    return FakeSkills()


@pytest.fixture
def searcher() -> FakeSearch:
    return FakeSearch(
        Hit(title="Kerberos", url="https://example.test/kerberos", snippet="A ticket protocol."),
        Hit(title="TGT", url="https://example.test/tgt", snippet="The ticket-granting ticket."),
    )


@pytest.fixture
def scratchpad() -> FakeScratchpad:
    return FakeScratchpad()


@pytest.fixture
def artifacts() -> FakeArtifacts:
    return FakeArtifacts()


@pytest.fixture
def wired(
    memories: FakeMemories,
    notes: FakeNotes,
    skills: FakeSkills,
    searcher: FakeSearch,
    scratchpad: FakeScratchpad,
    artifacts: FakeArtifacts,
) -> MCPServer:
    """Everything wired, which is what a v0.2 deployment looks like."""
    return build_builtin_server(
        memories=memories,
        notes=notes,
        skills=skills,
        searcher=searcher,
        scratchpad=scratchpad,
        artifacts=artifacts,
    )


@pytest.fixture
def wired_full(
    notes: FakeNotes,
    skills: FakeSkills,
    searcher: FakeSearch,
    scratchpad: FakeScratchpad,
    artifacts: FakeArtifacts,
) -> MCPServer:
    """A deployment whose memory has no room left, which is the one refusal with a next move
    written into it."""
    return build_builtin_server(
        memories=FakeMemories(full=True),
        notes=notes,
        skills=skills,
        searcher=searcher,
        scratchpad=scratchpad,
        artifacts=artifacts,
    )


@pytest.fixture
def bare() -> MCPServer:
    """Nothing wired, which is what v0.1 looks like."""
    return build_builtin_server()

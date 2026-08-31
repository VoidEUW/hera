"""The settings the application has to fill in, and that nothing else can.

`hera_chats` deliberately knows neither which tool suspends a turn nor which `_meta` key her
scratchpad reads a chat id from. Both arrive as strings from `hera_mcp` through
`hera_core.wiring`, which means both fail *silently* when they are forgotten: the turn runs,
every tool call succeeds, and the only symptom is her scratchpad answering "this call is not
part of a conversation" in the middle of a working conversation.

That is not hypothetical. The suite's own container is assembled by hand rather than by
`build_services`, and it was missing `chat_meta_key` until an end-to-end test found it — so
this file is the guard for the real assembly, which has nobody to notice on its behalf.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from hera_core.wiring import Services, build_services
from hera_mcp import ARTIFACT_META, ASK_TOOL, BUILTIN_SERVER_NAME, CHAT_ID_META
from hera_providers import FakeProvider
from hera_tools import ToolInvocation


@pytest.fixture
async def services() -> AsyncIterator[Services]:
    """The real assembly, against a fake model so nothing reaches an endpoint.

    `HERA_HOME` is repointed for every test in this suite, so `ToolRegistry.open` finds no
    `mcp.json` and mounts her own server and nothing else.
    """
    built = build_services(provider=FakeProvider([]))
    try:
        yield built
    finally:
        await built.aclose()


async def test_her_asking_tool_is_named_to_the_turn(services: Services) -> None:
    assert services.orchestrator.settings.asking_tools == (f"{BUILTIN_SERVER_NAME}__{ASK_TOOL}",)


async def test_the_chat_id_key_is_named_to_the_turn(services: Services) -> None:
    """Empty here means every scratchpad call arrives without a conversation, and the failure
    reads as a broken tool rather than as a missing line of wiring (ADR 12)."""
    assert services.orchestrator.settings.chat_meta_key == CHAT_ID_META


async def test_the_scratchpad_port_is_wired(services: Services) -> None:
    """The other half of the same mistake: the key can travel correctly to a server that has no
    scratchpad behind it, and the tool then answers *not available in this deployment* for a
    reason nobody reading the conversation can find.

    Driven through the real registry rather than by inspecting the wiring, because what is
    being asserted is that the call works — a `build_builtin_server(scratchpad=...)` argument
    can be present and be `None`.
    """
    assert services.registry is not None
    result = await services.registry.dispatch(
        ToolInvocation(
            call_id="c1",
            tool=f"{BUILTIN_SERVER_NAME}__scratch_write",
            arguments={"name": "plan.md", "text": "x"},
        ),
        context={CHAT_ID_META: "0f9c1c2e-1111-4222-8333-444444444444"},
    )

    assert result.ok, result.text


async def test_the_artifacts_port_is_wired_and_answers_with_a_card(services: Services) -> None:
    """The same guard for ADR 13, and it asserts one thing more: that the structured content the
    card is drawn from survives the whole path — her server, the client, the registry.

    That is the part with somebody else's behaviour in it. The tool returns text *and* JSON in
    one result; if the SDK or `hera_tools` dropped the second, every artifact would still be
    written correctly and none of them would ever appear on screen.
    """
    assert services.registry is not None
    result = await services.registry.dispatch(
        ToolInvocation(
            call_id="c2",
            tool=f"{BUILTIN_SERVER_NAME}__artifact_create",
            arguments={"name": "page.html", "content": "<h1>Hi</h1>", "inline": False},
        ),
        context={CHAT_ID_META: "0f9c1c2e-1111-4222-8333-444444444444"},
    )

    assert result.ok, result.text
    assert result.structured == {ARTIFACT_META: {"name": "page.html", "inline": False, "bytes": 11}}

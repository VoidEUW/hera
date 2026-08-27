"""The end-to-end suite: a real browser against the real application.

Real in every way except the model. The server is a real uvicorn process serving the real built
interface, talking to a real SQLite file — and a `FakeProvider` reading from a script, so the
whole path from a keystroke to a rendered emotion card runs in CI with no endpoint anywhere.

Marked ``e2e`` and deselected by the fast loop. It needs `npm run build` to have run; without a
built interface there is nothing to drive, and the fixtures say so rather than failing somewhere
confusing.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from hera_providers import (
    FakeProvider,
    TextDelta,
    ThinkingDelta,
    TurnEnd,
    text_turn,
    tool_call,
)

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "apps" / "core" / "src" / "hera_core" / "static"

pytestmark = pytest.mark.e2e

SCRIPT = [
    # One turn that reasons, speaks, and shows a stance -- which is the everyday shape, and the
    # one worth driving a browser for: three different variants landing in three different
    # places on the same message.
    [
        ThinkingDelta(text="They want the short version, not the RFC."),
        TextDelta(text="Kerberos issues a ticket-granting ticket, "),
        TextDelta(text="then service tickets against it.\n\n"),
        # Markdown and TeX, because that is the notation a model answers in and the interface
        # typesets it (ADR 11). The `---` sits directly under a line on purpose: that is the
        # setext trap, and it must come out as a rule rather than promoting "Cost" to a heading.
        TextDelta(text="- the TGT is cached\n- every service ticket derives from it\n\n"),
        TextDelta(text="**Cost**\n---\nThe lifetime is \\(t_0 + \\Delta\\).\n\n"),
        tool_call("hera__emotion", {"kind": "curious", "text": "Which part matters to you?"}),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("Ask me for the detail on whichever step you need."),
    # Enough turns for a test that edits a question and tries an answer again. The script
    # raises rather than repeating when it runs out, so a loop asking for more than this is a
    # bug in the loop and says so.
    text_turn("Shorter: one ticket buys the rest."),
    text_turn("Once more, then."),
]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture(scope="session")
def built_interface() -> Path:
    if not (STATIC / "index.html").is_file():
        pytest.skip("the interface has not been built — run `npm run build` in apps/core/web")
    return STATIC


@pytest.fixture
def server(
    built_interface: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """A real server on a free port, with its own data directory.

    Its own, because the suite writes chats and edits mind regions, and a test that mutates the
    developer's ~/.hera is a test nobody runs twice.
    """
    from hera_core.app import create_app
    from hera_core.boot import prepare
    from hera_core.settings import CoreSettings
    from hera_core.wiring import build_services

    home = tmp_path_factory.mktemp("hera-home")
    monkeypatch.setenv("HERA_HOME", str(home))

    # One skill on disk, so the composer's picker has something to switch on. Written rather
    # than mocked: the picker reads the same catalogue every other screen does.
    skill = home / "skills" / "tdd"
    skill.mkdir(parents=True)
    skill.joinpath("SKILL.md").write_text(
        "---\nname: tdd\ndescription: 'Use when you want tests first.'\n---\nRed, green.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERA_STORAGE_URL", f"sqlite:///{home / 'hera.sqlite3'}")

    settings = CoreSettings()
    services = build_services(settings, provider=FakeProvider(SCRIPT), registry=None)
    prepare(services.database, services.mind, owner_id=settings.owner_id)

    port = free_port()
    config = uvicorn.Config(
        create_app(settings, services=services), host="127.0.0.1", port=port, log_level="warning"
    )
    running = uvicorn.Server(config)
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 20
    while not running.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not running.started:
        raise RuntimeError("the server did not start")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        running.should_exit = True
        thread.join(timeout=10)

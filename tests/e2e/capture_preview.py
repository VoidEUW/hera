"""Film the interface for a pull request: screenshots plus a video of one full turn.

Not a test — there is nothing to assert, only things to look at. It uses the same machinery as
the end-to-end suite (the real built interface, a real uvicorn server, a scripted fake model,
no live endpoint anywhere) but writes media into an output directory instead of passing or
failing. CI runs it for every pull request and attaches the results to the run, so a reviewer
can see the branch on screen without checking it out.

    uv run python tests/e2e/capture_preview.py preview-media

It needs `npm run build` to have run in apps/core/web, exactly like the e2e suite.
"""

from __future__ import annotations

import argparse
import asyncio
import socket
import threading
import time
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import uvicorn
from hera_providers.events import Event
from hera_providers.request import ChatRequest
from playwright.sync_api import Page, sync_playwright

from hera_providers import FakeProvider, ThinkingDelta, TurnEnd, text_turn, tool_call

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "apps" / "core" / "src" / "hera_core" / "static"

# The waiting mark's feather-eye breath runs a four-second cycle; every scripted answer is
# held back long enough for the video to show it go round once, and for the walkthrough's
# look at it to never land after the mark has already gone.
WAIT_FLOOR = 4.0

SCRIPT: list[list[Event]] = [
    [
        ThinkingDelta(text="The ticket dance, kept to the moving parts. Hold the intro down."),
        *text_turn(
            "Kerberos hands you a **ticket-granting ticket** once, ",
            "and derives a service ticket from it for each service you touch.\n\n",
            "The TGT is what expires; the service tickets are downstream of it.",
        ),
    ],
    [
        ThinkingDelta(text="Checking whether the deployment can look up the lifetimes."),
        tool_call("hera__search", {"query": "kerberos ticket lifetime"}),
        ThinkingDelta(text="Nothing is wired here, so the call comes back empty. Answer anyway."),
        tool_call("hera__docs", {"query": "ticket-granting ticket expiry rules"}),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn(
        "Short version: one TGT buys every service ticket, ",
        "and the expiry you configure lives on the TGT.",
    ),
]


class PacedProvider(FakeProvider):
    """A FakeProvider that takes its time.

    The stock fake fires the whole script at once, which is right for assertions and wrong for
    filming: the waiting mark would be a frame at most. This one waits before the first event
    of every turn and breathes between the rest, so the waiting animation and the streamed
    answer are actually on screen.
    """

    def __init__(
        self,
        script: Sequence[Any],
        *,
        hold_turns: Sequence[int] | None = None,
        stream_delay: float = 0.25,
    ) -> None:
        super().__init__(script)
        self._holdings = None if hold_turns is None else set(hold_turns)
        self._stream_delay = stream_delay

    async def stream(self, request: ChatRequest) -> AsyncIterator[Event]:
        turn_index = len(self.requests)
        first = True
        async for event in super().stream(request):
            if first and (self._holdings is None or turn_index in self._holdings):
                await asyncio.sleep(WAIT_FLOOR)
                first = False
            else:
                await asyncio.sleep(self._stream_delay)
            yield event


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def serve(home: Path) -> tuple[str, uvicorn.Server, threading.Thread]:
    """The real app on a free port, with its own disposable home."""
    import os

    from hera_core.app import create_app
    from hera_core.boot import prepare
    from hera_core.settings import CoreSettings
    from hera_core.wiring import build_services

    os.environ["HERA_HOME"] = str(home)
    os.environ["HERA_STORAGE_URL"] = f"sqlite:///{home / 'hera.sqlite3'}"

    settings = CoreSettings()
    services = build_services(settings, provider=PacedProvider(SCRIPT), registry=None)
    prepare(services.database, services.mind, owner_id=settings.owner_id)

    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(settings, services=services),
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 20
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("the server did not start")
    return f"http://127.0.0.1:{port}", server, thread


def shoot(page: Page, directory: Path, name: str, *, full: bool = False) -> None:
    page.screenshot(path=directory / f"{name}.png", full_page=full)


def walk(page: Page, base: str, directory: Path) -> str:
    """The scenes, in order: empty start, the waiting mark mid-breath, answers, a trace."""
    page.goto(base, wait_until="networkidle")
    shoot(page, directory, "01-start")

    composer = page.locator("textarea").first
    composer.fill("Explain Kerberos")
    composer.press("Enter")
    page.wait_for_url("**/chat/**", timeout=15_000)

    # The waiting mark, two samples a little under half its four-second cycle apart, so one
    # frame catches the feather and one catches the eye; the video covers the whole loop. A
    # waiting mark that trips on a slow runner is not worth failing the whole shoot for, so if
    # it never shows we carry on and catch the answer instead.
    try:
        page.wait_for_selector(".waiting", timeout=15_000)
        page.wait_for_timeout(1400)
        shoot(page, directory, "02-waiting-feather")
        page.wait_for_timeout(1900)
        shoot(page, directory, "03-waiting-eye")
    except Exception:
        page.wait_for_selector("text=ticket-granting ticket", timeout=60_000)

    page.wait_for_selector("text=ticket-granting ticket", timeout=30_000)
    page.wait_for_selector("text=downstream of it", timeout=15_000)
    shoot(page, directory, "04-first-answer")

    # A second question with a long reasoning trace: enough rows to trip the collapse, then the
    # collapsed summary is expanded by hand so both states get a frame.
    composer = page.locator("textarea").first
    composer.fill("And what about the lifetimes?")
    composer.press("Enter")
    page.wait_for_selector("text=one TGT buys every service ticket", timeout=40_000)
    shoot(page, directory, "05-long-trace-collapsed", full=True)

    page.locator(".gutter.long .summary").first.click(timeout=5_000)
    shoot(page, directory, "06-long-trace-open", full=True)

    return page.url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="preview-media")
    args = parser.parse_args()
    out = Path(args.output)
    shots = out / "screenshots"
    videos = out / "videos"
    shots.mkdir(parents=True, exist_ok=True)
    videos.mkdir(parents=True, exist_ok=True)

    if not (STATIC / "index.html").is_file():
        raise SystemExit(
            "the interface has not been built — run `npm run build` in apps/core/web first"
        )

    import tempfile

    home = Path(tempfile.mkdtemp(prefix="hera-preview-"))
    base, server, thread = serve(home)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()

            desktop = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=2,
                record_video_dir=str(videos),
                record_video_size={"width": 1920, "height": 1080},
            )
            chat_url = walk(desktop.new_page(), base, shots)
            desktop.close()

            for label in ("phone",):
                mobile = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    device_scale_factor=3,
                )
                page = mobile.new_page()
                page.goto(base, wait_until="networkidle")
                shoot(page, shots, f"07-start-{label}")
                page.goto(chat_url, wait_until="networkidle")
                page.wait_for_selector("text=ticket-granting ticket", timeout=15_000)
                shoot(page, shots, f"08-answer-{label}")
                mobile.close()

            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    print(f"media written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Film the interface for a pull request, and record what the browser said while it did.

Not a test — there is nothing to assert, only things to look at. It uses the same machinery as
the end-to-end suite (the real built interface, a real uvicorn server, a scripted fake model, no
live endpoint anywhere) but writes media and a report into an output directory instead of passing
or failing. CI runs it for every pull request and attaches the results to the run, so a reviewer
can see the branch on screen without checking it out.

    uv run python tests/e2e/capture_preview.py preview-media

It needs ``npm run build`` to have run in apps/core/web, exactly like the e2e suite.

**What is recorded, and why each thing is here:**

* **Screenshots and a video for every scene**, at both widths. A change that only shows on the
  phone, or only in the light theme, is invisible in a desktop dark screenshot.
* **The console, page errors and failed requests**, per context, into ``console.log``. This is the
  part issue #122 asked for and did not get: that bug -- a first message lost between the start
  screen and the chat -- was unprovable because nothing recorded what the browser reported. A
  screenshot cannot show a console error and a silent 4xx is precisely the class of bug that
  looks like nothing happening.
* **A manifest** of every scene: ran or not, how long it took, and what failed. One broken scene
  must not cost the reviewer the other thirty, so each is guarded independently and the run always
  produces the report.

**A scene that throws is recorded and stepped over, never fatal.** The one thing that does stop
the run is a missing build, because then there is nothing to film and a directory of empty
screenshots would be worse than a clear failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import tempfile
import threading
import time
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import uvicorn
from hera_providers.events import Event
from hera_providers.request import ChatRequest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from hera_providers import (
    FakeProvider,
    ProviderError,
    StreamInterrupted,
    TextDelta,
    ThinkingDelta,
    TurnEnd,
    text_turn,
    tool_call,
)

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "apps" / "core" / "src" / "hera_core" / "static"

#: The waiting mark's feather-eye breath runs a four-second cycle; every scripted answer is
#: held back long enough for the video to show it go round once, and for the walkthrough's
#: look at it to never land after the mark has already gone.
WAIT_FLOOR = 4.0

#: A turn that never starts, because the endpoint refused the request. The transcript's note for
#: it is the difference between "she had nothing to say" and "the provider refused", and only one
#: of those is worth rewording the question for.
REFUSAL = ProviderError("the endpoint refused this request")

#: A turn cut off *after* some of it arrived, which is a different state with a different note:
#: what did arrive is kept, and the reason is `cancelled` rather than `failed`. This is what
#: navigating away mid-answer leaves behind, and it is the shape most likely to be got wrong.
CUT = StreamInterrupted("the connection dropped part way through")

#: A turn is either a whole failure or a list of events that may include one -- see
#: ``hera_providers.fake.Turn``, which this mirrors rather than imports, because the type is not
#: re-exported and a private import would be worse than the two words.
#:
#: ``Sequence`` and not ``list``, deliberately: a list is invariant, so a turn written as a plain
#: list of events would not be a ``list`` that also admits an ``Exception`` in it -- and every
#: turn here is written as a list, because that is the shape the fake is given.
Turn = Sequence[Event | Exception] | Exception


SCRIPT: Sequence[Turn] = [
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
    # A turn that never starts.
    REFUSAL,
    # And one that starts and is then cut off, so both notes get a frame.
    [*text_turn("This began, and then the connection "), CUT],
    text_turn("Still here. Neither of those ended the conversation."),
    # And one where she asks before answering, which stops the turn until a person replies. The
    # tool is never run, so nothing has to be wired for the card to appear.
    [
        TextDelta(text="Before I summarise it - "),
        tool_call("hera__ask", {"question": "Which deck do you mean?", "kind": "unsure"}),
        TurnEnd(reason="tool_calls"),
    ],
    # Which she then carries on with, the reply having become the result of her own call.
    text_turn("The 2024 one, then: three slides on ticket lifetime."),
]


class PacedProvider(FakeProvider):
    """A FakeProvider that takes its time, and can fail one turn on purpose.

    The stock fake fires the whole script at once, which is right for assertions and wrong for
    filming: the waiting mark would be a frame at most. This one waits before the first event of
    every turn and breathes between the rest, so the waiting animation and the streamed answer are
    actually on screen.

    A script entry that is an ``Exception`` is raised at the head of that turn rather than streamed,
    and one that *contains* an ``Exception`` is raised when the turn reaches it -- so the script can
    film a turn that never starts and a turn that is cut off part way through, which are two
    different states with two different notes.
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


# -- recording ---------------------------------------------------------------------------


@dataclass
class Scene:
    name: str
    group: str
    ok: bool = False
    seconds: float = 0.0
    problem: str = ""


@dataclass
class Report:
    """What every scene did, and what the browser said in each context.

    The console half exists because a screenshot cannot show a message and a request that 404s
    looks exactly like a request that never happened -- which is the whole of issue #122.
    """

    scenes: list[Scene] = field(default_factory=list)
    console: list[dict[str, str]] = field(default_factory=list)
    page_errors: list[dict[str, str]] = field(default_factory=list)
    failed_requests: list[dict[str, str]] = field(default_factory=list)

    def attach(self, page: Page, context: str) -> None:
        """Record everything the browser says on one page.

        Attached to the page rather than the context so the label is the page's, which is what a
        reader wants when looking at a line: *which screen said this*.
        """

        def on_console(message: Any) -> None:
            where = message.location
            self.console.append(
                {
                    "context": context,
                    "type": message.type,
                    "text": message.text,
                    "location": f"{where.get('url', '')}:{where.get('lineNumber', '')}",
                }
            )

        def on_error(error: Exception) -> None:
            self.page_errors.append({"context": context, "text": str(error)})

        def on_failed(request: Any) -> None:
            self.failed_requests.append(
                {
                    "context": context,
                    "method": request.method,
                    "url": request.url,
                    "failure": (request.failure or "")[:300],
                }
            )

        def on_response(response: Any) -> None:
            # A status is the only place a 4xx/5xx becomes visible, and `requestfailed` does not
            # fire for one: a 500 is a perfectly successful request that came back unhappy.
            if response.status >= 400:
                self.failed_requests.append(
                    {
                        "context": context,
                        "method": response.request.method,
                        "url": response.url,
                        "failure": f"HTTP {response.status}",
                    }
                )

        page.on("console", on_console)
        page.on("pageerror", on_error)
        page.on("requestfailed", on_failed)
        page.on("response", on_response)

    @contextmanager
    def scene(self, name: str, group: str, page: Page, shots: Path) -> Iterator[None]:
        """One scene, guarded, and photographed where it died.

        A scene that throws is recorded with its problem and stepped over, because the value of
        this run is the scenes that *did* work and a reviewer should not lose thirty of them to the
        thirty-first.

        The page and the screenshot directory are arguments rather than something each scene
        passes to a helper, and that is the whole point of the signature: an earlier version had
        every scene wrap its own steps in ``try``/``except: pass`` and then ask whether it had
        succeeded, which made a scene that did *nothing at all* report success. Twenty-two green
        scenes and nine missing screenshots is worse than nine red ones, because the red ones get
        looked at. A failure has to be able to escape the body for this to record one.
        """
        record = Scene(name=name, group=group)
        started = time.monotonic()
        try:
            yield
        except Exception as problem:  # a scene is never worth losing the run over
            record.problem = describe(problem)
            with suppress(PlaywrightError):
                page.screenshot(path=shots / f"FAILED-{name}.png", full_page=False)
        else:
            record.ok = True
        finally:
            record.seconds = round(time.monotonic() - started, 2)
            self.scenes.append(record)

    def write(self, out: Path) -> None:
        """The manifest and the console log, both plain text so a diff shows what changed."""
        ran = [s for s in self.scenes if s.ok]
        broken = [s for s in self.scenes if not s.ok]
        summary = {
            "ok": not broken,
            "scenes": len(self.scenes),
            "ran": len(ran),
            "did_not_run": len(broken),
            "console_messages": len(self.console),
            "page_errors": len(self.page_errors),
            "failed_requests": len(self.failed_requests),
            "screenshots": sorted(p.name for p in (out / "screenshots").glob("*.png")),
            "videos": sorted(p.name for p in (out / "videos").glob("*.webm")),
            "detail": [s.__dict__ for s in self.scenes],
        }
        (out / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        lines = ["# browser console", ""]
        for entry in self.console:
            lines.append(
                f"[{entry['context']}] {entry['type']}: {entry['text']}  ({entry['location']})"
            )
        lines += ["", "# uncaught page errors", ""]
        for entry in self.page_errors:
            lines.append(f"[{entry['context']}] {entry['text']}")
        lines += ["", "# failed requests (network failure or a 4xx/5xx)", ""]
        for entry in self.failed_requests:
            lines.append(
                f"[{entry['context']}] {entry['method']} {entry['url']} -> {entry['failure']}"
            )
        if not self.page_errors and not self.failed_requests:
            lines.append("(none)")
        (out / "console.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def describe(problem: BaseException) -> str:
    """One line about an exception, safe for an exception with nothing to say.

    ``str(exc).splitlines()[0]`` is the obvious way to take the first line, and it raises
    ``IndexError`` on an exception whose message is the empty string -- ``KeyError()`` and
    ``TimeoutError()`` both do it. That is a crash *inside the handler that exists so a run
    survives*, so the run does not survive it, and the report is never written. The type name
    alone is worth more than losing all of it.
    """
    lines = str(problem).splitlines()
    first = lines[0][:200] if lines else ""
    return f"{type(problem).__name__}: {first}" if first else type(problem).__name__


def shoot(page: Page, directory: Path, name: str, *, full: bool = False) -> None:
    page.screenshot(path=directory / f"{name}.png", full_page=full)


# -- the scenes --------------------------------------------------------------------------


def act_conversation(page: Page, base: str, shots: Path, report: Report) -> str:
    """The scripted turn: start page, the waiting mark mid-breath, an answer, a long trace."""
    chat_url = base
    with report.scene("01-start", "conversation", page, shots):
        page.goto(base, wait_until="networkidle")
        shoot(page, shots, "01-start")

    composer = page.locator("textarea").first
    with report.scene("02-waiting-mark", "conversation", page, shots):
        composer.fill("Explain Kerberos")
        composer.press("Enter")
        page.wait_for_url("**/chat/**", timeout=15_000)
        chat_url = page.url
        # Two samples a little under half the four-second cycle apart, so one frame catches the
        # feather and one catches the eye; the video covers the whole loop. A mark that trips on a
        # slow runner is not worth losing the scene for, so a miss here waits for the answer
        # instead and the scene is recorded as the miss it is.
        try:
            page.wait_for_selector(".waiting", timeout=15_000)
            page.wait_for_timeout(1400)
            shoot(page, shots, "02-waiting-feather")
            page.wait_for_timeout(1900)
            shoot(page, shots, "03-waiting-eye")
        except (PlaywrightTimeout, PlaywrightError) as missed:
            page.wait_for_selector("text=ticket-granting ticket", timeout=60_000)
            raise AssertionError(f"the waiting mark was never caught: {missed}") from missed

    with report.scene("03-first-answer", "conversation", page, shots):
        page.wait_for_selector("text=ticket-granting ticket", timeout=30_000)
        page.wait_for_selector("text=downstream of it", timeout=15_000)
        shoot(page, shots, "04-first-answer")

    with report.scene("04-long-trace", "conversation", page, shots):
        page.locator("textarea").first.fill("And what about the lifetimes?")
        page.locator("textarea").first.press("Enter")
        page.wait_for_selector("text=one TGT buys every service ticket", timeout=40_000)
        shoot(page, shots, "05-long-trace-collapsed", full=True)
        page.locator(".gutter.long .summary").first.click(timeout=5_000)
        page.wait_for_timeout(400)
        shoot(page, shots, "06-long-trace-open", full=True)

    with report.scene("05-a-turn-that-cannot-start", "conversation", page, shots):
        # The refusal note. A provider that errors must leave a sentence saying so, because the
        # alternative reads as an empty answer and invites a rewording of the question.
        page.locator("textarea").first.fill("And one more thing?")
        page.locator("textarea").first.press("Enter")
        page.wait_for_selector(".note", timeout=40_000)
        shoot(page, shots, "07-turn-refused")

    with report.scene("06-a-turn-cut-off-mid-answer", "conversation", page, shots):
        # A different state with a different note: some of the answer arrived and is kept, and the
        # reason is `cancelled` rather than `failed`. This is what navigating away mid-answer
        # leaves behind, and it is the shape most likely to be got wrong -- a naive fix discards the
        # half that did arrive.
        page.locator("textarea").first.fill("And now the connection?")
        page.locator("textarea").first.press("Enter")
        page.wait_for_selector("text=This began, and then", timeout=40_000)
        page.wait_for_timeout(800)
        shoot(page, shots, "08-turn-cut-off", full=True)

    with report.scene("07-the-answer-after-both", "conversation", page, shots):
        # Both of the two notes above, and then an ordinary answer: the point of the pair is that
        # neither of them ends the conversation.
        page.locator("textarea").first.fill("Are you still there?")
        page.locator("textarea").first.press("Enter")
        page.wait_for_selector("text=Neither of those ended", timeout=40_000)
        shoot(page, shots, "09-answer-after-both")

    return chat_url


def act_question(page: Page, chat_url: str, shots: Path, report: Report) -> None:
    """The question card: a turn stopped, waiting for a person, and resumed by their reply.

    ``hera__ask`` is the one tool that is never run -- ``hera_chats`` recognises it by name and
    suspends the turn, so a person's reply becomes that call's result. Nothing has to be wired for
    the card to appear, which is what makes it worth filming: it is the shape a turn takes when
    she is unsure, and it is the only place the composer is deliberately disabled.
    """
    with report.scene("10-the-question-card", "cards", page, shots):
        page.goto(chat_url, wait_until="networkidle")
        page.locator("textarea").first.fill("Summarise the deck")
        page.locator("textarea").first.press("Enter")
        page.wait_for_selector("text=Which deck do you mean?", timeout=40_000)
        # The kind of question, said in the person's words rather than the tool's (ADR 17).
        page.wait_for_selector("text=she is unsure", timeout=10_000)
        shoot(page, shots, "13-the-question-card")

    with report.scene("11-the-reply-resumes-the-turn", "cards", page, shots):
        reply = page.locator("aside textarea").first
        reply.fill("The 2024 one.")
        reply.press("Enter")
        page.wait_for_selector("text=three slides on ticket lifetime", timeout=40_000)
        shoot(page, shots, "14-the-reply-resumed")


def act_rail(page: Page, base: str, shots: Path, report: Report) -> None:
    """The rail's own states, which the conversation scenes never show."""
    with report.scene("rail-row-menu", "rail", page, shots):
        page.goto(base, wait_until="networkidle")
        page.wait_for_selector("nav.rail li.item", timeout=15_000)
        shoot(page, shots, "15-rail")
        page.locator("nav.rail button.more").first.click(timeout=5_000)
        page.wait_for_timeout(300)
        shoot(page, shots, "16-rail-menu")
        page.keyboard.press("Escape")

    with report.scene("rail-new-chat-and-projects", "rail", page, shots):
        # **New chat** goes to the start screen rather than making a chat, so what is being filmed
        # here is that decision: the rail's other button, and the start screen it lands on.
        page.get_by_role("button", name="New chat", exact=True).first.click(timeout=5_000)
        page.wait_for_timeout(400)
        shoot(page, shots, "17-new-chat-is-the-start-screen")


def act_composer(page: Page, base: str, shots: Path, report: Report) -> None:
    """The controls in the composer's bar, each opened.

    A dropdown's *open* state is where its own styling lives, and a reviewer looking at a closed
    pill cannot see a change to it.
    """
    with report.scene("composer-model-dropdown", "composer", page, shots):
        page.goto(base, wait_until="networkidle")
        page.locator(".bar .model button.pill").first.click(timeout=5_000)
        page.wait_for_selector("[role='listbox']", timeout=5_000)
        page.wait_for_timeout(300)
        shoot(page, shots, "20-model-dropdown")
        page.keyboard.press("Escape")

    with report.scene("composer-servers-sheet", "composer", page, shots):
        page.locator("button.context.servers").first.click(timeout=5_000)
        page.wait_for_selector("[role='dialog']", timeout=5_000)
        page.wait_for_timeout(500)
        shoot(page, shots, "21-servers-sheet")
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

    with report.scene("composer-skills-sheet", "composer", page, shots):
        page.locator("button.context.skills").first.click(timeout=5_000)
        page.wait_for_selector("[role='dialog']", timeout=5_000)
        page.wait_for_timeout(500)
        shoot(page, shots, "22-skills-sheet")
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

    with report.scene("composer-typed-and-growing", "composer", page, shots):
        field = page.locator("textarea").first
        field.fill("A question long enough that the field has to grow past its first line")
        page.wait_for_timeout(400)
        shoot(page, shots, "23-composer-grown")
        field.fill("")


#: The nav in the order the interface puts it, which `test_settings_is_one_size` asserts
#: separately. Filmed by position rather than by name, because a name is a string in a
#: translation file and a position is not.
SETTINGS_TABS = (
    "Account",
    "Models",
    "General",
    "Skills",
    "Servers",
    "Permissions",
    "Memory",
    "Mind",
    "Dreaming",
)


def settled(page: Page) -> None:
    """Wait for the Settings panel to stop being a loading placeholder.

    Settings fetches its three data sets for itself and draws `Rows` -- bars of grey -- while it
    does, so a screenshot taken in that window is a picture of a spinner, not of the screen. The
    wait is on `aria-busy`, which is the part of the placeholder that means "not ready" and is a
    promise rather than a style; a `wait_for_timeout` here is a guess, and a guess is what put
    two loading screenshots in the walkthrough.
    """
    page.wait_for_selector("[role='dialog'] [aria-busy='true']", state="detached", timeout=15_000)


def act_settings(page: Page, base: str, shots: Path, report: Report) -> None:
    """Every tab of the largest screen in the interface.

    Settings is where a great deal of work lands and where a single screenshot of the first tab
    tells a reviewer nothing about the other six.
    """
    with report.scene("settings-open", "settings", page, shots):
        page.goto(base, wait_until="networkidle")
        page.get_by_role("button", name="Settings").first.click(timeout=5_000)
        page.wait_for_selector("[role='dialog']", timeout=10_000)
        settled(page)
        shoot(page, shots, "30-settings-account")

    nav = page.locator("[role='dialog'] nav.tabs")
    for index, tab in enumerate(SETTINGS_TABS[1:], start=1):
        with report.scene(f"settings-{tab.lower()}", "settings", page, shots):
            # Not `exact`: **Dreaming** is labelled with a `v0.3` badge beside it, so its accessible
            # name is not the word on its own. Scoping the locator to the nav is what keeps a
            # substring match from hitting a row in the panel below.
            nav.get_by_role("button", name=tab).click(timeout=5_000)
            # The panel swaps in on a fetch, and a shot taken during the swap shows the old tab's
            # rows under the new tab's name -- which is the one thing this scene must not do.
            settled(page)
            page.wait_for_timeout(700)
            shoot(page, shots, f"3{index}-settings-{tab.lower()}", full=True)

    with report.scene("settings-search", "settings", page, shots):
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Settings").first.click(timeout=5_000)
        page.wait_for_selector("[role='dialog'] input", timeout=5_000)
        settled(page)
        page.locator("[role='dialog'] input").first.fill("kerberos")
        page.wait_for_timeout(600)
        shoot(page, shots, "39-settings-search")


def act_profile(page: Page, base: str, shots: Path, report: Report) -> None:
    """Settings → General, and the light theme it carries.

    Light is a whole palette rather than an inversion, and the control for it is not in Settings:
    it is on the General screen, reached through the card at the bottom of the rail.
    """
    with report.scene("profile-menu", "theme", page, shots):
        page.goto(base, wait_until="networkidle")
        page.locator("nav.rail button.card").first.click(timeout=5_000)
        page.wait_for_selector("[role='dialog']", timeout=10_000)
        page.get_by_role("button", name="General", exact=True).click(timeout=5_000)
        page.wait_for_timeout(500)
        shoot(page, shots, "40-profile-menu")

    with report.scene("light-theme", "theme", page, shots):
        # The change is asserted in both directions. A screenshot of the light theme is
        # indistinguishable from a screenshot of the dark one if the run happened to start light,
        # and that is precisely the run where the scene would be quietly worthless.
        assert page.evaluate("() => document.documentElement.dataset.theme") == "dark"
        page.get_by_role("button", name="Light", exact=True).first.click(timeout=5_000)
        page.wait_for_timeout(700)
        assert page.evaluate("() => document.documentElement.dataset.theme") == "light"
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        shoot(page, shots, "41-light-start")

    with report.scene("back-to-dark", "theme", page, shots):
        page.locator("nav.rail button.card").first.click(timeout=5_000)
        page.wait_for_selector("[role='dialog']", timeout=10_000)
        page.get_by_role("button", name="General", exact=True).click(timeout=5_000)
        page.get_by_role("button", name="Dark", exact=True).first.click(timeout=5_000)
        page.wait_for_timeout(500)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        # Proof rather than intention: the attribute is what the stylesheet keys off, so a
        # screenshot that merely *looks* dark proves nothing about whether it stayed dark.
        assert page.evaluate("() => document.documentElement.dataset.theme") == "dark"
        shoot(page, shots, "42-back-to-dark")


def act_reduced_motion(page: Page, base: str, shots: Path, report: Report) -> None:
    """Motion off, shown on the two gestures the CSS override cannot reach.

    `docs/frontend.md` claims reduced motion "removes every transition". A `transition:` is
    switched off by the media query for free; a Svelte transition is a `requestAnimationFrame`
    loop that never asks, so a sheet and a dropdown are the two places the claim can be false
    and both are fixed in `motion.ts` -- which makes them the two worth a frame. A still Settings
    sheet would prove nothing about either, and says nothing at all about the sheet *arriving*.
    """
    with report.scene("reduced-motion", "accessibility", page, shots):
        page.goto(base, wait_until="networkidle")
        page.get_by_role("button", name="Settings").first.click(timeout=5_000)
        page.wait_for_selector("[role='dialog']", timeout=10_000)
        settled(page)
        shoot(page, shots, "50-reduced-motion-settings")
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

    with report.scene("reduced-motion-drawer", "accessibility", page, shots):
        # The second of the two, and the one a person meets most: a dropdown that arrives
        # instantly rather than sliding.
        page.locator(".bar .model button.pill").first.click(timeout=5_000)
        page.wait_for_selector("[role='listbox']", timeout=5_000)
        page.wait_for_timeout(300)
        shoot(page, shots, "51-reduced-motion-dropdown")
        page.keyboard.press("Escape")


def act_mobile(page: Page, base: str, shots: Path, report: Report, chat_url: str) -> None:
    """The phone, filmed as well as shot -- including the off-canvas rail."""
    with report.scene("phone-start", "phone", page, shots):
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(500)
        shoot(page, shots, "70-phone-start")

    with report.scene("phone-rail", "phone", page, shots):
        page.locator("button.menu").first.click(timeout=5_000)
        page.wait_for_timeout(500)
        shoot(page, shots, "71-phone-rail")

    with report.scene("phone-answer", "phone", page, shots):
        page.keyboard.press("Escape")
        page.goto(chat_url, wait_until="networkidle")
        page.wait_for_selector("text=ticket-granting ticket", timeout=20_000)
        page.wait_for_timeout(500)
        shoot(page, shots, "72-phone-answer")

    with report.scene("phone-settings", "phone", page, shots):
        page.locator("button.menu").first.click(timeout=5_000)
        page.wait_for_timeout(400)
        page.get_by_role("button", name="Settings").first.click(timeout=5_000)
        page.wait_for_selector("[role='dialog']", timeout=10_000)
        settled(page)
        page.wait_for_timeout(500)
        shoot(page, shots, "73-phone-settings")


# -- the run -----------------------------------------------------------------------------


def name_recording(videos: Path, already: set[Path], label: str) -> set[Path]:
    """Rename the recording a just-closed context wrote to ``<label>.webm``.

    Playwright flushes the file on ``close()`` and names it after a random page id, so the
    recording is identified by being the one file in the directory that was not there before.
    Returns the names now taken, for the next context to exclude.
    """
    fresh = sorted(set(videos.glob("*.webm")) - already - {videos / f"{label}.webm"})
    if not fresh:
        return already
    latest = max(fresh, key=lambda path: path.stat().st_mtime)
    latest.replace(videos / f"{label}.webm")
    return already | set(videos.glob("*.webm"))


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

    report = Report()
    home = Path(tempfile.mkdtemp(prefix="hera-preview-"))
    base, server, thread = serve(home)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()

            # Playwright names a recording after a random page id, so `videos/*.webm` sorted is
            # not an ordering of anything -- it is an ordering of coin tosses. The first version
            # had the publishing job take `head -1` of that glob, which with one video was merely
            # fragile and with two is a coin toss deciding whether a reviewer watches the desktop
            # or the phone. Naming them here is what makes the name mean something.
            filmed: set[Path] = set()

            desktop = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=2,
                record_video_dir=str(videos),
                record_video_size={"width": 1920, "height": 1080},
                # Every context in this run says `color_scheme="dark"`, and deliberately at the
                # browser rather than in the application. The default appearance is `system`, and
                # `system` resolves through `prefers-color-scheme` -- so left alone the whole run
                # comes out light on a machine or a CI image that prefers light, dark on one that
                # does not, and the light-theme scenes below stop being a change at all. Emulating
                # the media query fixes the environment instead of the setting, which is the honest
                # direction to fix it in: the application keeps its own default and the runner is
                # made to say what it means.
                color_scheme="dark",
            )
            page = desktop.new_page()
            report.attach(page, "desktop")
            # Straight-line, and the order is the script's order: `FakeProvider` serves turns from
            # one shared list by index, so which turn a scene gets is decided by how many prompts
            # the scenes before it sent. A tuple of callables with a `chat_url` plucked out of
            # whatever came back hid exactly that, and the question card below cannot be in such a
            # tuple anyway because it needs the chat the first scene made.
            chat_url = act_conversation(page, base, shots, report)
            act_question(page, chat_url, shots, report)
            for act in (act_rail, act_composer, act_settings, act_profile):
                act(page, base, shots, report)
            desktop.close()
            filmed |= name_recording(videos, filmed, "desktop")

            # Reduced motion is its own context: the media query is read at the browser level, and
            # emulating it on a page that has already loaded does not retroactively stop the
            # transitions that are already running. No video: the point of the scene is that
            # nothing moves, and thirty seconds of a still screen is thirty seconds of nothing.
            still = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=2,
                reduced_motion="reduce",
                color_scheme="dark",
            )
            still_page = still.new_page()
            report.attach(still_page, "reduced-motion")
            act_reduced_motion(still_page, base, shots, report)
            still.close()

            # The phone gets a video too. The first version recorded one and screenshotted the
            # other, which meant a motion change was only reviewable on a screen a reviewer does
            # not have.
            mobile = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=3,
                record_video_dir=str(videos),
                record_video_size={"width": 390, "height": 844},
                color_scheme="dark",
            )
            mobile_page = mobile.new_page()
            report.attach(mobile_page, "phone")
            act_mobile(mobile_page, base, shots, report, chat_url)
            mobile.close()
            filmed |= name_recording(videos, filmed, "phone")

            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    report.write(out)

    ran = [s for s in report.scenes if s.ok]
    broken = [s for s in report.scenes if not s.ok]
    print(f"media written to {out}")
    print(f"  scenes ran          : {len(ran)}/{len(report.scenes)}")
    print(f"  console messages    : {len(report.console)}")
    print(f"  uncaught page errors: {len(report.page_errors)}")
    print(f"  failed requests     : {len(report.failed_requests)}")
    for scene in broken:
        print(f"  did not run: {scene.name} -- {scene.problem}")
    # Always zero. A scene that fails is reported in the manifest, printed above, and written into
    # the step summary -- and the job's verdict belongs to the checks, not to a screenshot. A
    # missing frame is worth knowing about; it is not a reason to throw away the other thirty.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

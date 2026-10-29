"""Stop ends the turn (#216).

The button was drawn, wired and aborted the request, and nothing on screen changed: the stream
was dropped on the floor, the question stayed in its waiting state, and the button stayed a Stop
button because the composer is `busy` for as long as the question is pending. A person pressing
it saw an answer that froze and a control that did not answer back.

Driven slowly (`stream_delay`) because a scripted turn normally lands in one piece, and there is
nothing to stop in an answer that has already finished.
"""

from __future__ import annotations

from typing import Any

import pytest
from e2e_support import Served

from hera_providers import text_turn

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

LONG = text_turn(*(f"word{n} " for n in range(200)), "THE LAST WORD.")


@pytest.fixture
def script() -> list[Any]:
    return [LONG, text_turn("A fresh answer, after the stop.")]


@pytest.fixture
def stream_delay() -> float:
    return 0.05


@pytest.fixture
def page(server: Served) -> Any:
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        server.sign_in(context)
        opened = context.new_page()
        opened.goto(server, wait_until="networkidle")
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def test_stop_ends_the_answer_and_gives_the_composer_back(page: Any) -> None:
    composer = page.locator("textarea").first
    composer.fill("Talk for a long time")
    composer.press("Enter")
    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=word5", timeout=15_000)

    page.get_by_role("button", name="Stop").click()

    # The control answers: it is a Send button again, and the composer takes a message.
    page.get_by_role("button", name="Send").wait_for(timeout=10_000)
    assert page.locator("textarea:not([disabled])").count() >= 1

    # What arrived is kept, marked as interrupted, and it stops growing.
    page.get_by_text("Interrupted").wait_for(timeout=10_000)
    assert page.get_by_text("THE LAST WORD.").count() == 0
    before = page.locator("article.hers").inner_text()
    page.wait_for_timeout(600)
    assert page.locator("article.hers").inner_text() == before
    assert "word5" in before

    # It is what the server kept, not an artefact of this tab.
    page.reload(wait_until="networkidle")
    page.get_by_text("Interrupted").wait_for(timeout=10_000)
    assert "word5" in page.locator("article.hers").first.inner_text()

    # And the conversation carries on.
    composer = page.locator("textarea:not([disabled])").first
    composer.fill("Go on")
    composer.press("Enter")
    page.wait_for_selector("text=A fresh answer, after the stop.", timeout=15_000)

"""Nothing in the browser console, through the path a person actually walks.

`effect_update_depth_exceeded` is this project's recurring injury: an effect that reads the state
it writes, which Svelte answers by giving up on rendering and leaving a blank page with nothing on
it to say why. It is written down four times in the source (`+layout.svelte`, `project/[id]`, the
artifact effect in `chat/[id]`, `Workspace.#persisted`) and until now it had no test -- every time
it landed it was found by a person looking at a white screen, or by a `wait_for_selector` somewhere
else timing out sixty seconds later with no clue in the failure.

So: drive the ordinary path and read the console. It is a blunt test and that is the point -- it
does not know what it is looking for, only that a healthy page says nothing.
"""

from __future__ import annotations

from typing import Any

import pytest

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

#: Chromium reports blocked resources and the like as console errors too, and none of those are
#: this interface's business. Everything Svelte says about its own runtime is.
INTERESTING = ("effect_update_depth_exceeded", "svelte", "Uncaught", "TypeError", "ReferenceError")


@pytest.fixture
def complaints(server: str) -> Any:
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        said: list[str] = []
        page.on(
            "console", lambda m: said.append(f"{m.type}: {m.text}") if m.type == "error" else None
        )
        page.on("pageerror", lambda e: said.append(f"pageerror: {e}"))
        try:
            yield page, said
        finally:
            context.close()
            browser.close()


def test_a_turn_from_the_start_screen_says_nothing_in_the_console(
    server: str, complaints: Any
) -> None:
    """The handoff path: the start screen creates the chat, navigates, and sends into it.

    Chosen because it is the one that crosses the most state at once -- a chat created, a message
    held in the store across a navigation, a transcript loading behind a placeholder, and a turn
    streaming into it. If an effect is going to eat itself, it is here.
    """
    page, said = complaints
    page.goto(server, wait_until="networkidle")

    composer = page.locator("textarea").first
    composer.fill("Explain Kerberos")
    composer.press("Enter")

    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=ticket-granting ticket", timeout=30_000)

    # And back out to the start screen and into the rail, because leaving a chat tears the
    # session down and that is the other half of the same machinery.
    page.get_by_role("link", name="Hera").first.click()
    page.wait_for_selector("textarea", timeout=10_000)

    loud = [line for line in said if any(word in line for word in INTERESTING)]
    assert not loud, "\n".join(loud)

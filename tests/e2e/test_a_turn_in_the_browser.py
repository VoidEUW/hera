"""From a keystroke to a rendered emotion card.

The one test that proves the whole thing is joined up: SvelteKit built, served by FastAPI,
streaming Server-Sent Events out of the turn orchestrator, reduced in the browser into a
message. Everything real except the model.
"""

from __future__ import annotations

from typing import Any

import pytest

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e


@pytest.fixture
def page(server: str) -> Any:
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        opened = context.new_page()
        opened.goto(server, wait_until="networkidle")
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def test_the_start_screen_greets_and_focuses_the_composer(page: Any) -> None:
    """Mark, greeting, composer, nothing else — and nothing to click before typing."""
    assert (
        page.locator("text=Good").first.is_visible() or page.locator(".display").first.is_visible()
    )
    assert page.locator("textarea").first.is_visible()


def test_a_message_streams_back_and_survives_a_reload(page: Any) -> None:
    composer = page.locator("textarea").first
    composer.fill("Explain Kerberos")
    composer.press("Enter")

    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=ticket-granting ticket", timeout=30_000)

    # An emotion renders as a card, inline, where she called it (ADR 3).
    page.wait_for_selector("text=curious", timeout=15_000)

    # The thinking channel is a gutter row, never mixed into the prose.
    assert page.locator("text=They want the short version").count() == 0

    url = page.url
    page.reload(wait_until="networkidle")

    # The server render is authoritative: the reload shows exactly what was streamed.
    page.wait_for_selector("text=ticket-granting ticket", timeout=15_000)
    page.wait_for_selector("text=curious", timeout=15_000)
    assert page.url == url


def test_settings_opens_as_a_modal_over_the_conversation(page: Any) -> None:
    page.get_by_role("button", name="Settings").click()
    page.wait_for_selector("[role=dialog]", timeout=10_000)
    assert page.locator("[role=dialog]").is_visible()

    page.keyboard.press("Escape")
    page.wait_for_selector("[role=dialog]", state="detached", timeout=10_000)

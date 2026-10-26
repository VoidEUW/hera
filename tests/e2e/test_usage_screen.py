"""Settings → Usage (#111): what her answers cost, day by day, in the browser."""

from __future__ import annotations

import re
from typing import Any

import pytest

from hera_providers import Usage, text_turn

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e


@pytest.fixture
def script() -> list[Any]:
    return [
        text_turn(
            "Counted.",
            usage=Usage(
                prompt_tokens=12000, completion_tokens=345, total_tokens=12345, cached_tokens=9000
            ),
        )
    ]


@pytest.fixture
def stream_delay() -> float:
    """A little time between fragments, so there is a writing time to measure a speed over."""
    return 0.02


@pytest.fixture
def page(server: str) -> Any:
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        opened = context.new_page()
        opened.goto(server, wait_until="networkidle")
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def open_usage(page: Any) -> Any:
    page.get_by_role("button", name="Settings").first.click()
    page.get_by_role("navigation", name="Settings").get_by_role("button", name="Usage").click()
    panel = page.locator("[role=dialog]")
    panel.locator("dl.totals").wait_for(timeout=15_000)
    return panel


def test_a_fresh_install_says_there_is_nothing_yet(page: Any) -> None:
    panel = open_usage(page)

    assert panel.get_by_text("Nothing yet.").count() == 1
    assert panel.get_by_role("slider").count() == 0
    # The totals are still there, at nought: a screen that drops its numbers when they are
    # zero leaves a person wondering whether it worked.
    assert panel.locator("dl.totals dd strong").all_inner_texts() == ["0 tokens"] * 3
    # Nothing measured, so no rate and no speed: a nought would be a claim nobody made.
    assert panel.get_by_text("cached").count() == 0
    assert panel.get_by_text("tok/s").count() == 0


def test_an_answer_is_a_bar_today_and_in_every_total(page: Any) -> None:
    composer = page.locator("textarea").first
    composer.fill("Count this")
    composer.press("Enter")
    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=Counted.", timeout=15_000)

    panel = open_usage(page)
    chart = panel.get_by_role("slider", name="Tokens per day, the last 30 days")
    chart.wait_for(timeout=10_000)

    # Today is the bar being read before anybody points at one.
    assert chart.get_attribute("aria-valuenow") == "30"
    assert "12,000 read, 345 written" in (chart.get_attribute("aria-valuetext") or "")
    assert panel.locator("dl.totals dd strong").all_inner_texts() == ["12,345 tokens"] * 3
    # What the endpoint said about its cache, and what Hera's own clock measured.
    assert panel.get_by_text("75% of what she read was cached").count() == 3
    assert panel.get_by_text(re.compile(r"tok/s · first token after")).count() == 3

    # The keyboard reads the day before, which had nothing.
    chart.focus()
    chart.press("ArrowLeft")
    assert chart.get_attribute("aria-valuenow") == "29"
    assert re.search(r": 0 read, 0 written$", chart.get_attribute("aria-valuetext") or "")


def test_a_screen_that_cannot_load_says_so_and_can_try_again(page: Any) -> None:
    """A 500 used to be one grey line reading `500 Internal Server Error`. It is now the error
    page at pane size: the status, what it means, what the server said, and a way back."""
    failing = {"on": True}

    def answer(route: Any) -> None:
        if failing["on"]:
            route.fulfill(status=500, json={"detail": "no such column: chat_usage.source"})
        else:
            route.continue_()

    page.route("**/api/v1/usage?*", answer)
    page.get_by_role("button", name="Settings").first.click()
    page.get_by_role("navigation", name="Settings").get_by_role("button", name="Usage").click()

    panel = page.locator("[role=dialog]")
    alert = panel.get_by_role("alert")
    alert.wait_for(timeout=15_000)
    assert alert.get_by_text("500 · Server error").count() == 1
    assert alert.get_by_role("heading", name="Could not load usage").count() == 1
    alert.get_by_text("What the server said").click()
    assert alert.get_by_text("no such column: chat_usage.source").count() == 1

    failing["on"] = False
    alert.get_by_role("button", name="Try again").click()
    panel.locator("dl.totals").wait_for(timeout=15_000)
    assert panel.get_by_role("alert").count() == 0

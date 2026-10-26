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
            usage=Usage(prompt_tokens=12000, completion_tokens=345, total_tokens=12345),
        )
    ]


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

    # The keyboard reads the day before, which had nothing.
    chart.focus()
    chart.press("ArrowLeft")
    assert chart.get_attribute("aria-valuenow") == "29"
    assert re.search(r": 0 read, 0 written$", chart.get_attribute("aria-valuetext") or "")

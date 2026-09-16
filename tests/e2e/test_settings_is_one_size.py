"""Settings: every screen draws its shape first, and the sheet is the same size on all of them.

Two complaints with one cause. Each of the six screens fetched into an empty array on mount and
rendered its empty state meanwhile, so opening a tab said *there is nothing here* and then filled
in; and because the sheet sized itself to whatever the tab held, switching between them moved the
close button around under the pointer. The panel scrolls inside a fixed sheet now, and every
screen holds its rows' shape until it has them (#72, #115).
"""

from __future__ import annotations

from typing import Any

import pytest

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

WAITING = "[role='status'][aria-busy='true']"

#: In the order the nav lists them, ending back on Models -- which remounts, so it is a seventh
#: case rather than a repeat of the first.
SCREENS = ("Skills", "Servers", "Permissions", "Memory", "Mind", "Models")


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


def settings(page: Any) -> None:
    page.get_by_role("button", name="Settings").first.click()
    page.wait_for_selector("[role='dialog']", timeout=10_000)


def test_every_settings_screen_draws_its_shape_first(page: Any) -> None:
    settings(page)
    # Models is where it lands, so its placeholder is up before anything has been clicked.
    page.wait_for_selector(WAITING, timeout=5_000)

    for screen in SCREENS:
        # Gone first, so what is found below is this screen's placeholder and not the last one's.
        page.wait_for_selector(WAITING, state="detached", timeout=10_000)
        page.get_by_role("button", name=screen, exact=True).click()
        page.wait_for_selector(WAITING, timeout=5_000)


def test_the_sheet_is_one_size_whatever_is_in_it(page: Any) -> None:
    settings(page)

    sizes = {}
    for screen in (*SCREENS, "Dreaming"):
        # `Dreaming` carries a "v0.3" badge inside the button, so its accessible name is not
        # just the word; everything else is matched exactly.
        button = (
            page.get_by_role("button", name="Dreaming")
            if screen == "Dreaming"
            else page.get_by_role("button", name=screen, exact=True)
        )
        button.click()
        page.wait_for_selector(WAITING, state="detached", timeout=10_000)
        box = page.locator("[role='dialog']").bounding_box()
        sizes[screen] = (round(box["width"]), round(box["height"]), round(box["y"]))

    assert len(set(sizes.values())) == 1, sizes

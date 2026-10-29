"""An address that leads nowhere says so, inside the shell, with the way back (#141).

The server answers every unknown path with the application, so a mistyped link used to land on a
blank main area beside the sidebar: nothing said the address was wrong, and nothing offered a way
out of it. The router's error page is what says it now.
"""

from __future__ import annotations

from typing import Any

import pytest
from e2e_support import Served

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e


@pytest.fixture
def page(server: Served) -> Any:
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        server.sign_in(context)
        opened = context.new_page()
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def test_a_mistyped_address_says_nothing_is_there(server: Served, page: Any) -> None:
    page.goto(f"{server}/no-such-screen", wait_until="networkidle")

    page.get_by_role("heading", name="Nothing here").wait_for(timeout=15_000)
    # Inside the shell rather than instead of it: the sidebar is the other way out.
    assert page.get_by_role("navigation", name="Hera").count() == 1


def test_the_way_back_is_the_start_screen(server: Served, page: Any) -> None:
    page.goto(f"{server}/no-such-screen", wait_until="networkidle")

    page.get_by_role("button", name="Back to the start").click()

    page.wait_for_url(f"{server}/", timeout=10_000)
    assert page.get_by_role("heading", name="Nothing here").count() == 0

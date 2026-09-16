"""A dead server says so, instead of saying the account is empty.

With nothing listening behind it the interface still loads -- it is a static bundle, and only the
API is gone -- and it used to come up as a perfectly ordinary application reporting *No chats
yet.* and *No projects yet.* An empty list and a list that could not be fetched are the same empty
array in the browser, and telling somebody their conversations are gone because a process is not
running is the worst thing this interface could say.

The requests are refused rather than the server being stopped, which is the same thing from the
browser's side and leaves the fixture able to answer the retry.
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
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        opened = context.new_page()
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def refuse(page: Any) -> dict[str, bool]:
    """Turn the API off and on again from the browser's side."""
    listening = {"on": False}
    page.route(
        "**/api/v1/**",
        lambda route: route.continue_() if listening["on"] else route.abort("connectionrefused"),
    )
    return listening


def test_an_unreachable_server_is_not_an_empty_account(server: str, page: Any) -> None:
    refuse(page)
    page.goto(server)

    page.wait_for_selector("text=Hera is not answering", timeout=15_000)

    # Not one word about there being nothing here, and no chrome to click that cannot work.
    assert page.get_by_text("No chats yet.").count() == 0
    assert page.get_by_text("No projects yet.").count() == 0
    assert page.locator("nav.rail").count() == 0

    # What actually happened is on the screen, under the thing to do about it.
    assert page.get_by_role("button", name="Try again").count() == 1
    assert page.get_by_text("uv run hera serve").count() == 1


def test_try_again_brings_the_application_back(server: str, page: Any) -> None:
    listening = refuse(page)
    page.goto(server)
    page.wait_for_selector("text=Hera is not answering", timeout=15_000)

    listening["on"] = True
    page.get_by_role("button", name="Try again").click()

    # The rail, which means the load answered -- and no reload was needed to get here.
    page.wait_for_selector("nav.rail", timeout=15_000)
    assert page.get_by_text("Hera is not answering").count() == 0

"""Settings → Models: providers fold, a model row opens its own options, nothing is dashed.

Three complaints with one cause (#106). Every registered endpoint was drawn fully expanded, so the
one you came for was somewhere below the fold; a model's options opened from a small button and
stayed open beside others; and a dashed rule and a heading cut the models off from the provider
they belong to.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

API = "/api/v1"
WAITING = "[role='status'][aria-busy='true']"


@pytest.fixture
def page(server: str) -> Iterator[Any]:
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        opened = context.new_page()
        # A second endpoint, which starts closed because it is not the active one, and a second
        # model on the active one, so there is something for "one row open at a time" to mean.
        added = opened.request.post(
            f"{server}{API}/providers",
            data={"name": "studio", "base_url": "http://localhost:9/v1", "model_id": "m-one"},
        )
        assert added.ok, added.text()
        opened.goto(server, wait_until="networkidle")
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def models(page: Any) -> None:
    page.get_by_role("button", name="Settings").first.click()
    page.wait_for_selector("[role='dialog']", timeout=10_000)
    page.get_by_role("button", name="Models", exact=True).click()
    page.wait_for_selector(WAITING, state="detached", timeout=10_000)


def header(page: Any, name: str) -> Any:
    return page.locator(f"button.disclosure:has-text('{name}')")


def test_only_the_active_provider_is_open_and_the_rest_fold(page: Any) -> None:
    models(page)

    headers = page.locator("button.disclosure")
    assert headers.count() == 2
    opened = [h.get_attribute("aria-expanded") for h in headers.all()]
    assert sorted(opened) == ["false", "true"]
    # One endpoint's fields on screen, not two.
    assert page.get_by_text("Base URL", exact=True).count() == 1

    header(page, "studio").click()
    assert header(page, "studio").get_attribute("aria-expanded") == "true"
    assert page.get_by_text("Base URL", exact=True).count() == 2

    header(page, "studio").click()
    assert header(page, "studio").get_attribute("aria-expanded") == "false"


def test_what_you_opened_is_still_open_when_you_come_back(page: Any) -> None:
    models(page)
    header(page, "studio").click()

    page.get_by_role("button", name="Skills", exact=True).click()
    page.get_by_role("button", name="Models", exact=True).click()
    page.wait_for_selector(WAITING, state="detached", timeout=10_000)

    assert header(page, "studio").get_attribute("aria-expanded") == "true"


def test_a_model_row_opens_its_own_options_and_only_one_at_a_time(page: Any, server: str) -> None:
    models(page)
    header(page, "studio").click()
    # Two models on one provider.
    page.request.post(f"{server}{API}/providers/studio/models", data={"id": "m-two"})
    page.get_by_role("button", name="Skills", exact=True).click()
    page.get_by_role("button", name="Models", exact=True).click()
    page.wait_for_selector(WAITING, state="detached", timeout=10_000)

    # There is no Options button any more.
    assert page.get_by_role("button", name="Options", exact=True).count() == 0

    studio = page.locator("section.entry:has(button.disclosure:has-text('studio'))")
    rows = studio.locator("button.toggle")
    assert rows.count() == 2

    rows.nth(0).click()
    assert rows.nth(0).get_attribute("aria-expanded") == "true"
    assert studio.get_by_text("Context window").count() == 1

    # Another row of the same provider takes over; the first closes.
    rows.nth(1).click()
    assert rows.nth(0).get_attribute("aria-expanded") == "false"
    assert rows.nth(1).get_attribute("aria-expanded") == "true"
    assert studio.get_by_text("Context window").count() == 1

    rows.nth(1).click()
    assert studio.get_by_text("Context window").count() == 0


def test_nothing_on_the_screen_is_a_dashed_rule(page: Any) -> None:
    models(page)
    header(page, "studio").click()

    dashed = page.evaluate(
        """() => [...document.querySelectorAll("[role='dialog'] *")]
            .filter((el) => getComputedStyle(el).borderTopStyle === 'dashed').length"""
    )
    assert dashed == 0

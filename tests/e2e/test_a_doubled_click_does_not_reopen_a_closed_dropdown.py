"""A dropdown that closes on an outside click must not reopen from the same gesture.

`Select.svelte`'s open dropdown is dismissed by a full-viewport catcher (`.away`) that sits above
everything, including the trigger pill itself — so while the dropdown is open, a click anywhere
on screen, even squarely on the pill, hits the catcher rather than the pill underneath. Closing
it removes it from the DOM, which exposes the pill again at the exact spot the catcher just
covered.

A worn mouse switch or a trackpad driver can deliver two native `click` events for one physical
click, sub-20ms apart. The first hits the catcher and closes the dropdown; the second, landing
a few ms later at the same coordinates, now resolves to the exposed pill and reopens what the
first event just closed. `toggle()` carries a short grace window against exactly this now, and
this test reproduces the doubled click directly rather than trusting real hardware timing.
"""

from __future__ import annotations

from typing import Any

import pytest

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

WAITING = "[role='status'][aria-busy='true']"


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


def test_a_doubled_click_does_not_reopen_a_closed_dropdown(page: Any) -> None:
    settings(page)
    page.wait_for_selector(WAITING, state="detached", timeout=10_000)

    # The "adding" section's own Kind selector, not a per-provider one: a fresh `HERA_HOME` has
    # no providers registered, so a per-provider row never renders, but "Add an endpoint" always
    # does once the placeholder is gone.
    page.get_by_role("button", name="Add an endpoint").click()
    trigger = page.locator("section.adding").get_by_role("button", name="Kind")
    trigger.wait_for(state="visible")

    trigger.click()
    page.wait_for_selector("[role='listbox']")

    box = trigger.bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    # Two native `click` events at the trigger's own coordinates, ~8ms apart, each aimed at
    # whatever element is topmost *at dispatch time* rather than a cached reference -- that
    # re-hit-test is the bug itself: the first click lands on `.away` (topmost while open) and
    # closes it, synchronously removing `.away` from the DOM; the second, a few ms later, must
    # therefore resolve to the now-exposed `.pill` underneath, exactly as a doubled native click
    # from a worn switch or driver would. Two Playwright `.click()` calls were rejected here:
    # their own actionability waits land them hundreds of ms apart, well outside the sub-20ms
    # window the bug report measured, so they would never exercise this race.
    page.evaluate(
        """([x, y]) => {
            const fire = () => document
                .elementFromPoint(x, y)
                .dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: x, clientY: y }));
            return new Promise((resolve) => {
                fire();
                setTimeout(() => {
                    fire();
                    resolve(null);
                }, 8);
            });
        }""",
        [cx, cy],
    )

    assert page.locator("[role='listbox']").count() == 0
    assert trigger.get_attribute("aria-expanded") == "false"

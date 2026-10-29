"""Settings → Permissions: make, change and remove rules, and keep them (#109).

What is asserted is what a person would check by hand — a rule made on the screen is there after
a reload and on disk, flipping it sticks, and delete asks first and one that ships with Hera has
no delete at all.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from e2e_support import Served, written

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e


@pytest.fixture
def page(server: Served) -> Any:
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        server.sign_in(context)
        opened = context.new_page()
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def stored(until: Callable[[dict[str, Any]], bool] = lambda _: True) -> dict[str, Any]:
    return written(Path(os.environ["HERA_HOME"]) / "permissions.json", until)


def open_permissions(page: Any, server: Served) -> None:
    page.goto(server, wait_until="networkidle")
    page.get_by_role("button", name="Settings").first.click(timeout=10_000)
    page.get_by_role("navigation", name="Settings").get_by_role(
        "button", name="Permissions"
    ).click()
    page.get_by_role("button", name="New rule").wait_for(timeout=10_000)


def row(page: Any, title: str) -> Any:
    return page.locator("section.row").filter(has=page.get_by_role("heading", name=title))


def test_a_rule_made_here_is_kept_flipped_and_deleted_after_asking(
    server: Served, page: Any
) -> None:
    open_permissions(page, server)

    page.get_by_role("button", name="New rule").click()
    page.get_by_label("Name").fill("Reading files")
    page.get_by_label("Applies to").fill("fs__read*")
    page.get_by_text("None of Hera\u2019s tools right now.").wait_for(timeout=5_000)
    page.get_by_role("dialog", name="New rule").get_by_role("radio", name="Allow").click()
    page.get_by_label("Why").fill("It only reads.")
    page.get_by_role("button", name="Add rule").click()

    made = row(page, "Reading files")
    made.wait_for(timeout=5_000)
    assert made.get_by_text("fs__read*").count() == 1
    assert made.get_by_role("radio", name="Allow").get_attribute("aria-checked") == "true"
    assert stored(lambda d: bool(d.get("rules")))["rules"][0]["name"] == "Reading files"

    # It survives a reload, and so is what the server holds rather than what the page remembers.
    page.reload(wait_until="networkidle")
    open_permissions(page, server)
    assert row(page, "Reading files").count() == 1

    row(page, "Reading files").get_by_role("radio", name="Deny").click()
    page.wait_for_function(
        "() => [...document.querySelectorAll('section.row')].some(r => "
        "r.textContent.includes('Reading files') && "
        "r.querySelector('[role=radio][aria-checked=true]')?.textContent.trim() === 'Deny')"
    )
    assert stored(lambda d: d["rules"][0]["decision"] == "deny")["rules"][0]["decision"] == "deny"

    row(page, "Reading files").get_by_role("button", name="Delete this rule").click()
    asked = page.get_by_role("dialog", name="Delete this rule?")
    asked.wait_for(timeout=5_000)
    asked.get_by_role("button", name="Keep it").click()
    assert row(page, "Reading files").count() == 1

    row(page, "Reading files").get_by_role("button", name="Delete this rule").click()
    page.get_by_role("dialog", name="Delete this rule?").get_by_role(
        "button", name="Delete"
    ).click()
    row(page, "Reading files").wait_for(state="detached", timeout=5_000)
    assert stored(lambda d: d["rules"] == [])["rules"] == []


def test_a_rule_that_ships_with_hera_can_be_changed_but_not_deleted(
    server: Served, page: Any
) -> None:
    open_permissions(page, server)

    shipped = row(page, "Every tool from hera")
    shipped.wait_for(timeout=5_000)

    assert shipped.get_by_text("Built in").count() == 1
    assert shipped.get_by_role("button", name="Delete this rule").count() == 0
    shipped.get_by_role("radio", name="Ask").click()
    page.wait_for_function(
        "() => [...document.querySelectorAll('section.row')].some(r => "
        "r.textContent.includes('Every tool from hera') && "
        "r.querySelector('[role=radio][aria-checked=true]')?.textContent.trim() === 'Ask')"
    )
    assert stored(lambda d: bool(d.get("rules")))["rules"][0]["pattern"] == "hera__*"


def test_the_form_says_which_tools_a_pattern_covers_before_it_is_added(
    server: Served, page: Any
) -> None:
    open_permissions(page, server)

    page.get_by_role("button", name="New rule").click()
    page.get_by_label("Applies to").fill("hera__*")

    page.get_by_text("of Hera\u2019s tools now:").wait_for(timeout=5_000)
    assert page.locator(".tool").filter(has_text="hera__note").count() == 1


def test_the_fallback_is_a_switch_and_is_kept(server: Served, page: Any) -> None:
    open_permissions(page, server)

    section = page.locator("section.fallback")
    section.get_by_role("radio", name="Deny").click()
    page.wait_for_function(
        "() => document.querySelector('section.fallback [role=radio][aria-checked=true]')"
        "?.textContent.trim() === 'Deny'"
    )

    assert stored(lambda d: d.get("fallback") == "deny")["fallback"] == "deny"


def test_a_pattern_that_is_already_a_rule_says_so_instead_of_replacing_it(
    server: Served, page: Any
) -> None:
    open_permissions(page, server)

    page.get_by_role("button", name="New rule").click()
    page.get_by_label("Applies to").fill("hera__*")
    page.get_by_role("button", name="Add rule").click()

    page.get_by_role("alert").filter(has_text="already a rule").wait_for(timeout=5_000)

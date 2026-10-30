"""Claiming a fresh Hera, signing out, and signing back in — in a real browser (ADR 27).

The one test that starts from a server nobody can sign in to. Every other test in the suite gets
an admin's session handed to it; this is the path that makes that admin.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from e2e_support import Served

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

EMAIL = "ada@example.org"
PASSWORD = "a long password"


@pytest.fixture
def claimed() -> bool:
    return False


@pytest.fixture
def page(server: Served) -> Any:
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        opened = context.new_page()
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def test_the_wizard_makes_the_admin_and_signing_out_and_in_works(server: Served, page: Any) -> None:
    expect = playwright.expect

    # An unclaimed instance sends everybody to the wizard, whatever they asked for.
    page.goto(f"{server}/chat/anything", wait_until="networkidle")
    page.wait_for_url("**/setup")

    # From the machine itself: no setup code is asked for.
    expect(page.get_by_label("Setup code")).to_have_count(0)
    page.get_by_label("Name").fill("Ada")
    page.get_by_label("Email").fill(EMAIL)
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Next").click()

    expect(page.get_by_text("What this Hera is")).to_be_visible()
    page.get_by_label("Name").fill("Home")
    page.get_by_role("button", name="Next").click()

    expect(page.get_by_text("Where she runs")).to_be_visible()
    page.get_by_role("button", name="Skip").click()

    page.get_by_role("button", name="Open Hera").click()
    page.wait_for_url(re.compile(r"/$"))
    account = page.get_by_role("button", name=re.compile(r"— Settings$"))
    expect(account).to_be_visible()

    # Signing out from the account row's menu lands on the sign-in card, named for this Hera.
    account.hover()
    page.get_by_role("button", name="Account options").click()
    page.get_by_role("menuitem", name="Sign out").click()
    page.wait_for_url("**/login")
    expect(page.get_by_role("heading", name="Sign in to Home")).to_be_visible()

    # Registration was left closed, so there is no tab offering it.
    expect(page.get_by_role("radio", name="Register")).to_have_count(0)

    page.get_by_label("Email").fill(EMAIL)
    page.get_by_label("Password").fill("not the password")
    page.get_by_role("button", name="Continue").click()
    expect(page.get_by_role("alert")).to_contain_text("do not match")

    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Continue").click()
    page.wait_for_url(re.compile(r"/$"))
    expect(page.get_by_role("button", name=re.compile(r"— Settings$"))).to_be_visible()

    # And a signed-out browser asking for a chat is sent to sign in, and back afterwards.
    page.context.clear_cookies()
    page.goto(f"{server}/project/elsewhere", wait_until="networkidle")
    page.wait_for_url("**/login?next=%2Fproject%2Felsewhere")

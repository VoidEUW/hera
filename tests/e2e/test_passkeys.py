"""Passkeys in a real browser, with Chromium's virtual authenticator (ADR 27, M4).

At ``localhost``, because WebAuthn takes a domain and a secure context: the same server opened at
``127.0.0.1`` offers no passkey at all, and that is checked too.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

import pytest
from e2e_support import Served

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e


def at_localhost(server: Served) -> str:
    return f"http://localhost:{urlsplit(str(server)).port}"


@pytest.fixture
def browser() -> Any:
    with playwright.sync_playwright() as driver:
        launched = driver.chromium.launch()
        try:
            yield launched
        finally:
            launched.close()


def with_authenticator(page: Any) -> None:
    """A platform authenticator that holds resident keys and verifies its user without asking."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("WebAuthn.enable")
    cdp.send(
        "WebAuthn.addVirtualAuthenticator",
        {
            "options": {
                "protocol": "ctap2",
                "transport": "internal",
                "hasResidentKey": True,
                "hasUserVerification": True,
                "isUserVerified": True,
                "automaticPresenceSimulation": True,
            }
        },
    )


def test_a_passkey_is_added_and_signs_in_with_no_email(server: Served, browser: Any) -> None:
    expect = playwright.expect
    base = at_localhost(server)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    from hera_core.auth import SESSION_COOKIE

    context.add_cookies([{"name": SESSION_COOKIE, "value": server.token, "url": base}])
    page = context.new_page()
    with_authenticator(page)

    page.goto(f"{base}/", wait_until="networkidle")
    page.get_by_role("button", name=re.compile(r"— Settings$")).click()
    page.get_by_role("button", name="Add a passkey").click()
    expect(page.get_by_text("Chrome on", exact=False)).to_be_visible()
    expect(page.get_by_text("Not used yet")).to_be_visible()

    # Rename it, so a list of them can be told apart.
    page.get_by_role("button", name="Rename").click()
    name = page.get_by_label(re.compile(r"^Name of "))
    name.fill("Test laptop")
    name.press("Enter")
    expect(page.get_by_text("Test laptop")).to_be_visible()

    # Signed out, the sign-in card offers the passkey, and it is the whole of signing in.
    page.get_by_role("button", name="Sign out", exact=True).click()
    page.wait_for_url("**/login")
    page.get_by_role("button", name="Sign in with a passkey").click()
    page.wait_for_url(re.compile(r"/$"))
    expect(page.get_by_role("button", name=re.compile(r"— Settings$"))).to_be_visible()

    # It was used, and removing it leaves none.
    page.get_by_role("button", name=re.compile(r"— Settings$")).click()
    expect(page.get_by_text(re.compile(r"^Last used "))).to_be_visible()
    page.get_by_role("button", name="Remove Test laptop").click()
    page.get_by_role("button", name="Delete", exact=True).click()
    expect(page.get_by_text("No passkeys yet.")).to_be_visible()


def test_at_an_ip_address_no_passkey_is_offered(server: Served, browser: Any) -> None:
    page = browser.new_context().new_page()
    page.goto(f"{server}/login", wait_until="networkidle")
    playwright.expect(page.get_by_role("button", name="Continue")).to_be_visible()
    playwright.expect(page.get_by_role("button", name="Sign in with a passkey")).to_have_count(0)

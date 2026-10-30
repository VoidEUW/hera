"""Invitations, password resets and mail, in a real browser (ADR 27, M3).

An admin invites somebody with no mail set up and hands the link over; the newcomer opens it in
a browser of their own, chooses a password and is in. Then mail is pointed at a sink on this
machine, and a forgotten password travels the whole way: asked for on the sign-in card, mailed,
opened, chosen.
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

import pytest
from e2e_support import OWNER_EMAIL, Served, mail_sink

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e


def as_admin(server: Served, method: str, path: str, payload: dict[str, Any]) -> None:
    request = urllib.request.Request(
        f"{server}/api/v1{path}",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", **server.headers},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


@pytest.fixture
def browser() -> Any:
    with playwright.sync_playwright() as driver:
        launched = driver.chromium.launch()
        try:
            yield launched
        finally:
            launched.close()


def fresh(browser: Any) -> Any:
    return browser.new_context(viewport={"width": 1280, "height": 900}).new_page()


def test_an_invitation_without_mail_is_a_link_somebody_opens(server: Served, browser: Any) -> None:
    expect = playwright.expect
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    admin = server.sign_in(context).new_page()
    admin.goto(f"{server}/", wait_until="networkidle")
    admin.get_by_role("button", name=re.compile(r"— Settings$")).click()
    admin.get_by_role("navigation", name="Settings").get_by_role("button", name="Users").click()

    admin.get_by_label("Email").fill("ben@example.org")
    admin.get_by_label("Name").fill("Ben")
    admin.get_by_role("button", name="Invite", exact=True).click()
    expect(admin.get_by_text("Copy this link and send it to them")).to_be_visible()
    expect(admin.get_by_text("Invited", exact=True)).to_be_visible()
    link = admin.locator(".sent code").inner_text()
    assert "/password#" in link

    newcomer = fresh(browser)
    newcomer.goto(link, wait_until="networkidle")
    expect(newcomer.get_by_role("heading", name="Welcome to Hera")).to_be_visible()
    newcomer.get_by_label("Password").fill("a long password")
    newcomer.get_by_role("button", name="Choose password").click()
    newcomer.wait_for_url(re.compile(r"/$"))
    expect(newcomer.get_by_role("button", name=re.compile(r"^Ben — Settings$"))).to_be_visible()

    # Spent: the same link a second time says so instead of offering a form.
    again = fresh(browser)
    again.goto(link, wait_until="networkidle")
    expect(again.get_by_role("heading", name="This link does not work any more")).to_be_visible()


def test_without_mail_a_forgotten_password_is_a_question_for_an_admin(
    server: Served, browser: Any
) -> None:
    page = fresh(browser)
    page.goto(f"{server}/login", wait_until="networkidle")
    page.get_by_role("button", name="Forgot your password?").click()
    playwright.expect(page.get_by_text("Ask an admin for a reset link")).to_be_visible()


def test_a_forgotten_password_is_mailed_opened_and_chosen(server: Served, browser: Any) -> None:
    expect = playwright.expect
    with mail_sink() as sink:
        as_admin(
            server,
            "PATCH",
            "/mail",
            {"host": "127.0.0.1", "port": sink.port, "security": "none", "sender": "h@hera.test"},
        )
        as_admin(server, "PATCH", "/instance", {"public_url": str(server)})

        page = fresh(browser)
        page.goto(f"{server}/login", wait_until="networkidle")
        page.get_by_role("button", name="Forgot your password?").click()
        page.get_by_label("Email").fill(OWNER_EMAIL)
        page.get_by_role("button", name="Send a link").click()
        expect(page.get_by_text("If there is an account for that address")).to_be_visible()

        text = sink.next_text()
        match = re.search(r"\S+/password#\S+", text)
        assert match, text
        assert match.group(0).startswith(str(server))

    page.goto(match.group(0), wait_until="networkidle")
    expect(page.get_by_role("heading", name="Choose a new password")).to_be_visible()
    page.get_by_label("Password").fill("a brand new password")
    page.get_by_role("button", name="Choose password").click()
    page.wait_for_url(re.compile(r"/$"))
    expect(page.get_by_role("button", name=re.compile(r"— Settings$"))).to_be_visible()


def test_an_admin_deletes_one_person_or_a_selection(server: Served, browser: Any) -> None:
    expect = playwright.expect
    for name in ("Ben", "Cy", "Dee"):
        as_admin(
            server, "POST", "/invitations", {"email": f"{name.lower()}@example.org", "name": name}
        )
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    admin = server.sign_in(context).new_page()
    admin.goto(f"{server}/", wait_until="networkidle")
    admin.get_by_role("button", name=re.compile(r"— Settings$")).click()
    admin.get_by_role("navigation", name="Settings").get_by_role("button", name="Users").click()
    dialog = admin.get_by_role("dialog")

    # One, from the button on their row.
    dialog.get_by_role("button", name="Delete Ben").click()
    expect(admin.get_by_text("Delete Ben?")).to_be_visible()
    admin.get_by_role("button", name="Delete", exact=True).click()
    expect(dialog.get_by_text("ben@example.org")).to_have_count(0)

    # Several, selected, with one confirmation. Your own row cannot be selected at all.
    expect(dialog.get_by_role("checkbox", name=re.compile(r"^Select owner"))).to_have_count(0)
    dialog.get_by_label("Select everybody shown").check()
    expect(dialog.get_by_text("2 selected")).to_be_visible()
    dialog.get_by_role("button", name="Delete selected").click()
    expect(admin.get_by_text("Delete 2 people?")).to_be_visible()
    admin.get_by_role("button", name="Delete", exact=True).click()
    expect(dialog.get_by_text("cy@example.org")).to_have_count(0)
    expect(dialog.get_by_text("dee@example.org")).to_have_count(0)
    expect(dialog.get_by_text(OWNER_EMAIL)).to_be_visible()


def test_a_link_is_copied_from_the_menu_and_the_mailed_one_stops(
    server: Served, browser: Any
) -> None:
    expect = playwright.expect
    as_admin(server, "POST", "/invitations", {"email": "eve@example.org", "name": "Eve"})
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.grant_permissions(["clipboard-read", "clipboard-write"], origin=str(server))
    admin = server.sign_in(context).new_page()
    admin.goto(f"{server}/", wait_until="networkidle")
    admin.get_by_role("button", name=re.compile(r"— Settings$")).click()
    admin.get_by_role("navigation", name="Settings").get_by_role("button", name="Users").click()

    admin.get_by_role("button", name="Actions for Eve").click()
    admin.get_by_role("menuitem", name="Copy a new invitation link").click()
    expect(admin.get_by_text("Link copied. Any link sent before no longer works.")).to_be_visible()
    shown = admin.locator(".sent code").inner_text()
    assert "/password#" in shown
    assert admin.evaluate("navigator.clipboard.readText()") == shown

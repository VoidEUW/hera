"""Two people on one Hera, in a real browser (ADR 28).

The admin opens registration and leaves a conversation and a memory behind; a second person
registers on the sign-in card and finds none of it — and none of the instance's screens either.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from e2e_support import Served

from hera_core.settings import CoreSettings

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e


def as_admin(server: Served, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{server}/api/v1{path}",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", **server.headers},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as answer:
        return dict(json.load(answer))


@pytest.fixture
def page(server: Served) -> Any:
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        # Not signed in: this browser is the second person.
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        opened = context.new_page()
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def test_a_second_person_sees_nothing_of_the_first(server: Served, page: Any) -> None:
    expect = playwright.expect

    chat = as_admin(server, "POST", "/chats", {"title": "The admin's own plans"})
    as_admin(server, "PATCH", "/instance", {"registration": "open"})
    owner = str(CoreSettings().owner_id)
    memories = Path(os.environ["HERA_HOME"]) / "users" / owner / "memories"
    memories.mkdir(parents=True, exist_ok=True)
    (memories / "likes-tea.md").write_text("---\ndescription: Tea\n---\nThey drink tea.\n")

    page.goto(f"{server}/login", wait_until="networkidle")
    page.get_by_role("radio", name="Register").click()
    page.get_by_label("Name").fill("Ben")
    page.get_by_label("Email").fill("ben@example.org")
    page.get_by_label("Password").fill("a long password")
    page.get_by_role("button", name="Create account").click()
    page.wait_for_url(re.compile(r"/$"))
    expect(page.get_by_role("button", name=re.compile(r"Ben — Settings$"))).to_be_visible()

    # Not in the rail, not at its address, not through the API.
    expect(page.get_by_text("The admin's own plans")).to_have_count(0)
    assert page.request.get(f"{server}/api/v1/chats/{chat['id']}").status == 404
    assert page.request.get(f"{server}/api/v1/memories").json() == []

    # The instance's routes refuse; their screens are not offered at all.
    elsewhere = {"base_url": "http://elsewhere"}
    assert page.request.delete(f"{server}/api/v1/servers/anything").status == 403
    assert page.request.patch(f"{server}/api/v1/providers/local", data=elsewhere).status == 403
    page.get_by_role("button", name=re.compile(r"— Settings$")).click()
    nav = page.get_by_role("navigation", name="Settings")
    expect(nav.get_by_role("button", name="Mind")).to_be_visible()
    for screen in ("Models", "Servers", "Skills"):
        expect(nav.get_by_role("button", name=screen)).to_have_count(0)

    # Their mind is theirs, and the instance's regions in it are read-only.
    nav.get_by_role("button", name="Mind").click()
    expect(page.get_by_role("textbox", name="Safety")).to_be_disabled()
    expect(page.get_by_role("textbox", name="Tone")).to_be_enabled()

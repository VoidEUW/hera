"""The rail holds the shape of a list rather than denying there is one.

Issue #72: on a cold load the sidebar rendered its genuine empty-state copy -- *No chats yet.*,
*No projects yet.* -- until `workspace.load()` answered, then flashed to the real list. An empty
list and a list that has not arrived are the same empty array in the browser, and only one of
them is something to say out loud.

These run against an ordinary load with nothing throttled, because that is the case that was
wrong twice: first by saying the wrong thing, then by saying nothing at all and dropping the
whole list in at once. The placeholder is drawn on the first frame and held a floor, so at local
speed it is still up when the assertions look for it.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

import pytest

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e


@pytest.fixture
def page(server: str) -> Any:
    """A browser that has *not* navigated yet -- these tests watch the first load."""
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        opened = context.new_page()
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def post(base: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base}/api/v1{path}",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as answer:
        return dict(json.load(answer))


def test_an_ordinary_load_draws_the_shape_of_the_rail(server: str, page: Any) -> None:
    post(server, "/projects", {"name": "Kerberos"})
    post(server, "/chats", {"title": "Ticket lifetimes"})

    page.goto(server)

    # Nothing is throttled here: if the placeholder had a delay to beat, a server on the same
    # machine would beat it and this would never appear.
    page.wait_for_selector("[role='status'][aria-label='Loading chats…']", timeout=10_000)
    assert page.get_by_text("No chats yet.").count() == 0
    assert page.get_by_text("No projects yet.").count() == 0

    page.wait_for_selector("text=Ticket lifetimes", timeout=15_000)
    page.wait_for_selector("text=Kerberos", timeout=15_000)


def test_the_placeholder_is_the_height_the_list_turns_out_to_be(server: str, page: Any) -> None:
    """The second load knows what the first one found, so the swap moves nothing.

    A placeholder sized from a guess is the same jump as no placeholder at all, pointed the
    other way -- which is what `Workspace.shape` remembers a count for.
    """
    for title in ("Ticket lifetimes", "Why the TGT is cached", "Clock skew", "Kerberos vs OIDC"):
        post(server, "/chats", {"title": title})

    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("text=Clock skew", timeout=15_000)
    settled = page.locator("ul.scroll").bounding_box()["height"]

    page.reload()
    page.wait_for_selector("[role='status'][aria-label='Loading chats…']", timeout=10_000)
    holding = page.locator("ul.scroll").bounding_box()["height"]

    # Within one row of the real thing, rather than within a guess of it.
    assert abs(holding - settled) < 32, f"placeholder {holding}px, list {settled}px"


def test_a_genuinely_empty_rail_still_says_so(server: str, page: Any) -> None:
    """The other half of the rule, and the one a guard this blunt could quietly break."""
    page.goto(server, wait_until="networkidle")

    page.wait_for_selector("text=No chats yet.", timeout=10_000)
    page.wait_for_selector("text=No projects yet.", timeout=10_000)


def test_a_project_opened_by_url_is_not_declared_missing_first(server: str, page: Any) -> None:
    """The same bug one screen over, and a worse sentence to be wrong about.

    A project the rail has not fetched yet and a project that does not exist are the same `null`
    on this page. Landing on `/project/<id>` used to answer *There is no such project.* first.
    """
    project = post(server, "/projects", {"name": "Kerberos"})

    page.goto(f"{server}/project/{project['id']}")

    page.wait_for_selector("[role='status'][aria-label='Loading the project…']", timeout=10_000)
    assert page.get_by_text("There is no such project.").count() == 0

    page.wait_for_selector("h1:has-text('Kerberos')", timeout=15_000)


def test_a_project_that_really_is_missing_still_says_so(server: str, page: Any) -> None:
    page.goto(f"{server}/project/2b0b4b4e-0000-4000-8000-000000000000", wait_until="networkidle")

    page.wait_for_selector("text=There is no such project.", timeout=10_000)

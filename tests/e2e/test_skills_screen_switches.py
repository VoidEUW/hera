"""Settings → Skills: a checkbox and an editor on each row, no usage count (#107)."""

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
        opened.goto(server, wait_until="networkidle")
        try:
            yield opened
        finally:
            # Left on, so the next test finds the seeded skill the way it was written.
            opened.request.patch(f"{server}{API}/skills/tdd", data={"enabled": True})
            context.close()
            browser.close()


def skills(page: Any) -> None:
    page.get_by_role("button", name="Settings").first.click()
    page.wait_for_selector("[role='dialog']", timeout=10_000)
    page.get_by_role("button", name="Skills", exact=True).click()
    page.wait_for_selector(WAITING, state="detached", timeout=10_000)


def test_a_skill_is_switched_off_and_stays_off(page: Any, server: str) -> None:
    skills(page)

    box = page.get_by_role("checkbox", name="Use tdd")
    assert box.is_checked()
    box.click()
    assert not box.is_checked()

    listed = page.request.get(f"{server}{API}/skills").json()["skills"]
    assert [(skill["id"], skill["enabled"]) for skill in listed] == [("tdd", False)]


def test_the_row_has_no_usage_count(page: Any) -> None:
    skills(page)

    dialog = page.get_by_role("dialog")
    assert dialog.get_by_text("Never used").count() == 0
    assert dialog.get_by_role("link", name="hera-skills repository").count() == 1


def test_a_skill_is_edited_in_place_over_settings(page: Any, server: str) -> None:
    skills(page)
    page.get_by_role("button", name="Edit tdd").click()

    editor = page.get_by_role("dialog", name="Edit tdd")
    editor.wait_for(timeout=10_000)
    box = editor.get_by_role("textbox", name="SKILL.md")
    assert "Red, green." in box.input_value()
    assert editor.get_by_role("button", name="Save").is_disabled()

    # The editor is the topmost sheet: Escape closes it and leaves Settings where it was.
    page.keyboard.press("Escape")
    editor.wait_for(state="detached", timeout=10_000)
    assert page.get_by_role("dialog", name="Settings").is_visible()

    page.get_by_role("button", name="Edit tdd").click()
    box = page.get_by_role("dialog", name="Edit tdd").get_by_role("textbox", name="SKILL.md")
    box.fill(box.input_value().replace("Red, green.", "Red, green, refactor."))
    page.get_by_role("dialog", name="Edit tdd").get_by_role("button", name="Save").click()
    page.get_by_role("dialog", name="Edit tdd").wait_for(state="detached", timeout=10_000)

    source = page.request.get(f"{server}{API}/skills/tdd/source").json()["content"]
    assert "Red, green, refactor." in source


def test_a_skill_is_created_in_the_editor_and_deleted_from_it(page: Any, server: str) -> None:
    skills(page)
    page.get_by_role("button", name="Add a skill").click()

    editor = page.get_by_role("dialog", name="New skill")
    editor.wait_for(timeout=10_000)
    assert editor.get_by_role("button", name="Create").is_disabled()
    editor.get_by_placeholder("note-taking").fill("Note-Taking")
    # The template follows the id for as long as nobody has edited it.
    assert "name: note-taking" in editor.get_by_role("textbox", name="SKILL.md").input_value()
    editor.get_by_role("button", name="Create").click()
    editor.wait_for(state="detached", timeout=10_000)

    ids = [s["id"] for s in page.request.get(f"{server}{API}/skills").json()["skills"]]
    assert "note-taking" in ids

    page.get_by_role("button", name="Edit note-taking").click()
    editor = page.get_by_role("dialog", name="Edit note-taking")
    editor.wait_for(timeout=10_000)
    editor.get_by_role("button", name="Delete", exact=True).click()
    # One click is not enough: it asks first, and nothing is gone yet.
    assert "note-taking" in [
        s["id"] for s in page.request.get(f"{server}{API}/skills").json()["skills"]
    ]
    editor.get_by_role("button", name="Delete skill").click()
    editor.wait_for(state="detached", timeout=10_000)

    ids = [s["id"] for s in page.request.get(f"{server}{API}/skills").json()["skills"]]
    assert "note-taking" not in ids
    assert page.get_by_role("button", name="Edit note-taking").count() == 0

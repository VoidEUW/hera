"""A person who spots a typo in something she published has a pen (#101), and the chat has a menu.

Two things the keyboard (#112) needs in order to have anything to mirror: **Save** in the side
view, and **Export / Share / Delete** under the chat's own top bar. What is asserted is the
behaviour a person would check by hand: the edit lands on disk and survives a reload, a draft is
not thrown away without asking, and a delete says what it will take.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
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


def post(base: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base}/api/v1{path}",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as answer:
        return dict(json.load(answer))


@pytest.fixture
def notes(server: str) -> tuple[str, Path]:
    """A chat that already published `notes.md`, so the side view reopens on it."""
    chat = post(server, "/chats", {"title": "Plans"})
    folder = Path(os.environ["HERA_HOME"]) / "chats" / str(chat["id"]) / "artifacts"
    folder.mkdir(parents=True)
    (folder / "notes.md").write_text("# Draft\n", encoding="utf-8")
    return str(chat["id"]), folder / "notes.md"


def test_an_edit_is_saved_and_survives_a_reload(
    server: str, page: Any, notes: tuple[str, Path]
) -> None:
    chat_id, file = notes
    page.goto(f"{server}/chat/{chat_id}")
    page.get_by_role("button", name="Edit this file").click(timeout=10_000)

    save = page.get_by_role("button", name="Save", exact=True)
    assert save.is_disabled(), "nothing has changed yet, so there is nothing to save"
    box = page.locator(".cv textarea.input")
    box.fill("# Final\n")
    assert save.is_enabled()
    save.click()

    page.get_by_text("Saved", exact=True).wait_for(timeout=5_000)
    assert file.read_text(encoding="utf-8") == "# Final\n"
    page.reload()
    page.get_by_role("button", name="Edit this file").click(timeout=10_000)
    assert page.locator(".cv textarea.input").input_value() == "# Final\n"


def test_an_unsaved_edit_is_not_thrown_away_without_asking(
    server: str, page: Any, notes: tuple[str, Path]
) -> None:
    chat_id, file = notes
    page.goto(f"{server}/chat/{chat_id}")
    page.get_by_role("button", name="Edit this file").click(timeout=10_000)
    page.locator(".cv textarea.input").fill("# Oops\n")

    page.locator("aside.drawer").get_by_role("button", name="Close").click()
    dialog = page.get_by_role("dialog", name="Discard your changes?")
    dialog.wait_for(timeout=5_000)
    dialog.get_by_role("button", name="Keep editing").click()
    dialog.wait_for(state="detached", timeout=5_000)
    assert page.locator(".cv textarea.input").input_value() == "# Oops\n"

    page.locator("aside.drawer").get_by_role("button", name="Close").click()
    page.get_by_role("dialog", name="Discard your changes?").get_by_role(
        "button", name="Discard"
    ).click()
    page.locator("aside.drawer").wait_for(state="detached", timeout=5_000)
    assert file.read_text(encoding="utf-8") == "# Draft\n", "discarding must not write"


def test_the_chat_menu_exports_greys_share_and_deletes_after_asking(
    server: str, page: Any, notes: tuple[str, Path]
) -> None:
    chat_id, _ = notes
    page.goto(f"{server}/chat/{chat_id}")
    page.get_by_role("button", name="Options for this chat").click(timeout=10_000)

    export = page.get_by_role("menuitem", name="Export")
    assert (export.get_attribute("href") or "").endswith(f"/chats/{chat_id}/export.md")
    assert page.get_by_role("menuitem", name="Share").is_disabled()

    page.get_by_role("menuitem", name="Delete").click()
    page.get_by_text("Delete this chat?").wait_for(timeout=5_000)
    page.get_by_role("menuitem", name="Delete").click()

    page.wait_for_url(f"{server}/", timeout=10_000)
    assert page.get_by_text("Plans").count() == 0

"""The keyboard (#112): every chord does what a control on screen already does.

Driven with `ControlOrMeta`, which is ⌘ on the macOS runner and Ctrl on Linux — the same
translation the keymap makes, so one test covers both. What is asserted is what a person would
check by hand: the key and the button end in the same place, and a key never steals typing.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from e2e_support import Served

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

MOD = "ControlOrMeta"


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


def post(base: Served, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base}/api/v1{path}",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", **base.headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as answer:
        return dict(json.load(answer))


def published(chat_id: str, name: str, text: str) -> Path:
    folder = Path(os.environ["HERA_HOME"]) / "chats" / chat_id / "artifacts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")
    return folder / name


def test_the_palette_finds_a_chat_by_name_and_opens_it(server: Served, page: Any) -> None:
    chat = post(server, "/chats", {"title": "Kerberos tickets"})
    post(server, "/chats", {"title": "Garden plans"})
    page.goto(server, wait_until="networkidle")

    page.keyboard.press(f"{MOD}+K")
    palette = page.get_by_role("dialog", name="Search and jump")
    palette.wait_for(timeout=5_000)
    assert palette.get_by_role("option", name="Garden plans").count() == 1

    page.keyboard.type("kerb")
    assert palette.get_by_role("option").filter(has_text="Garden").count() == 0
    page.keyboard.press("Enter")

    page.wait_for_url(f"**/chat/{chat['id']}", timeout=10_000)
    palette.wait_for(state="detached", timeout=5_000)


def test_the_sidebar_search_row_opens_the_same_palette(server: Served, page: Any) -> None:
    page.goto(server, wait_until="networkidle")

    page.get_by_role("button", name="Search chats").click()

    page.get_by_role("dialog", name="Search and jump").wait_for(timeout=5_000)


def test_the_palette_chats_chord_is_scoped_to_chats(server: Served, page: Any) -> None:
    post(server, "/chats", {"title": "Kerberos tickets"})
    page.goto(server, wait_until="networkidle")

    page.keyboard.press(f"{MOD}+Shift+F")

    palette = page.get_by_role("dialog", name="Search and jump")
    palette.wait_for(timeout=5_000)
    assert palette.get_by_placeholder("Search chats…").count() == 1
    assert palette.get_by_role("option", name="New chat").count() == 0


def test_settings_and_the_hotkeys_screen_have_their_own_chords(server: Served, page: Any) -> None:
    page.goto(server, wait_until="networkidle")

    page.keyboard.press(f"{MOD}+,")
    page.get_by_role("dialog", name="Settings").wait_for(timeout=5_000)
    page.keyboard.press("Escape")
    page.get_by_role("dialog", name="Settings").wait_for(state="detached", timeout=5_000)

    page.keyboard.press(f"{MOD}+/")
    settings = page.get_by_role("dialog", name="Settings")
    settings.wait_for(timeout=5_000)
    # Every chord, beside the control it mirrors.
    settings.get_by_text("Search and jump").wait_for(timeout=5_000)
    settings.get_by_text("Same as: Search in the sidebar").first.wait_for(timeout=5_000)


def test_new_chat_chord_goes_to_the_start_screen(server: Served, page: Any) -> None:
    chat = post(server, "/chats", {"title": "Plans"})
    page.goto(f"{server}/chat/{chat['id']}", wait_until="networkidle")

    page.keyboard.press(f"{MOD}+Shift+O")

    page.wait_for_url(f"{server}/", timeout=10_000)


def test_alt_arrows_walk_the_chats(server: Served, page: Any) -> None:
    first = post(server, "/chats", {"title": "First"})
    second = post(server, "/chats", {"title": "Second"})
    page.goto(f"{server}/chat/{first['id']}", wait_until="networkidle")
    page.locator("body").click(position={"x": 700, "y": 400})

    # The rail lists the most recently made first, so the other one is above or below.
    page.keyboard.press("Alt+ArrowUp")
    page.wait_for_url(f"**/chat/{second['id']}", timeout=10_000)
    page.keyboard.press("Alt+ArrowDown")
    page.wait_for_url(f"**/chat/{first['id']}", timeout=10_000)


def test_a_key_does_not_steal_typing_in_the_message_field(server: Served, page: Any) -> None:
    chat = post(server, "/chats", {"title": "Plans"})
    page.goto(f"{server}/chat/{chat['id']}", wait_until="networkidle")
    box = page.locator("textarea").first
    box.fill("one two three")

    # ⌥↑ and ⌘⌫ are cursor and line editing in a text field: they stay with the field.
    box.press("Alt+ArrowUp")
    box.press(f"{MOD}+Backspace")

    page.wait_for_timeout(300)
    assert page.url.endswith(f"/chat/{chat['id']}")
    assert page.get_by_text("Delete this chat?").count() == 0


def test_the_side_view_chord_toggles_it_and_escape_closes_it(server: Served, page: Any) -> None:
    chat = post(server, "/chats", {"title": "Plans"})
    published(chat["id"], "notes.md", "# Draft\n")
    page.goto(f"{server}/chat/{chat['id']}", wait_until="networkidle")
    drawer = page.locator("aside.drawer")
    drawer.wait_for(timeout=10_000)

    page.keyboard.press(f"{MOD}+.")
    drawer.wait_for(state="detached", timeout=5_000)
    page.keyboard.press(f"{MOD}+.")
    drawer.wait_for(timeout=5_000)

    page.locator("body").click(position={"x": 500, "y": 300})
    page.keyboard.press("Escape")
    drawer.wait_for(state="detached", timeout=5_000)


def test_escape_closes_a_menu_before_the_side_view(server: Served, page: Any) -> None:
    chat = post(server, "/chats", {"title": "Plans"})
    published(chat["id"], "notes.md", "# Draft\n")
    page.goto(f"{server}/chat/{chat['id']}", wait_until="networkidle")
    drawer = page.locator("aside.drawer")
    drawer.wait_for(timeout=10_000)

    page.get_by_role("button", name="Options for this chat").click()
    menu = page.get_by_role("menu", name="Options for this chat")
    menu.wait_for(timeout=5_000)
    page.keyboard.press("Escape")

    menu.wait_for(state="detached", timeout=5_000)
    assert drawer.count() == 1, "one Escape does one thing"


def test_save_has_a_chord_that_only_answers_when_there_is_something_to_save(
    server: Served, page: Any
) -> None:
    chat = post(server, "/chats", {"title": "Plans"})
    file = published(chat["id"], "notes.md", "# Draft\n")
    page.goto(f"{server}/chat/{chat['id']}", wait_until="networkidle")
    page.get_by_role("button", name="Edit this file").click(timeout=10_000)

    page.locator(".cv textarea.input").fill("# Final\n")
    page.keyboard.press(f"{MOD}+S")

    page.get_by_text("Saved", exact=True).wait_for(timeout=5_000)
    assert file.read_text(encoding="utf-8") == "# Final\n"


def test_export_and_delete_chords_mirror_the_chat_menu(server: Served, page: Any) -> None:
    chat = post(server, "/chats", {"title": "Plans"})
    page.goto(f"{server}/chat/{chat['id']}", wait_until="networkidle")
    page.locator("body").click(position={"x": 700, "y": 400})

    with page.expect_download(timeout=10_000) as download:
        page.keyboard.press(f"{MOD}+E")
    assert download.value.suggested_filename.endswith(".md")

    page.keyboard.press(f"{MOD}+Backspace")
    page.get_by_text("Delete this chat?").wait_for(timeout=5_000)
    page.get_by_role("menuitem", name="Delete").click()
    page.wait_for_url(f"{server}/", timeout=10_000)


def test_find_counts_matches_walks_them_and_closes_on_escape(server: Served, page: Any) -> None:
    page.goto(server, wait_until="networkidle")
    composer = page.locator("textarea").first
    composer.fill("Explain Kerberos")
    composer.press("Enter")
    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=Ask me for the detail", timeout=30_000)

    page.locator("body").click(position={"x": 700, "y": 200})
    page.keyboard.press(f"{MOD}+F")
    bar = page.get_by_role("search", name="Find in this chat")
    bar.wait_for(timeout=5_000)
    page.keyboard.type("ticket")

    count = bar.locator(".count")
    page.wait_for_function(
        "(el) => /^1 of \\d+$/.test(el.textContent.trim())", arg=count.element_handle()
    )
    first = count.inner_text()
    assert int(first.split()[-1]) >= 2, "the answer says ticket more than once"
    page.keyboard.press("Enter")
    assert count.inner_text().startswith("2 of")

    # The field's own Escape clears it first, then a second one closes the bar.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    bar.wait_for(state="detached", timeout=5_000)


def test_the_focus_chord_returns_to_the_message_field(server: Served, page: Any) -> None:
    chat = post(server, "/chats", {"title": "Plans"})
    page.goto(f"{server}/chat/{chat['id']}", wait_until="networkidle")
    page.locator("body").click(position={"x": 700, "y": 300})

    page.keyboard.press("Shift+Escape")

    assert page.evaluate("document.activeElement?.tagName") == "TEXTAREA"

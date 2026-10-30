"""The interface on a phone (#41): 390 by 844, touch, and nothing scrolls sideways.

The desktop is the shape the interface was designed in and the one every other file here drives.
This one asks what is left of it on a phone. Each assertion is a defect that was on screen
before #41:
- the composer's chips truncated to an ellipsis each;
- Settings was a card whose sections overlapped, with the rail still open behind it;
- the rail drew key chords on a device without keys;
- a text field small enough that iOS zooms the page into it.

A page that is wider than the screen is the one failure every screen can have, so it is asked
of every screen, Settings' included.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from e2e_support import Served

from hera_core.settings import CoreSettings

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

PHONE = {"width": 390, "height": 844}

#: Every screen the Settings list offers, Dreaming aside: it is listed and disabled until v0.3.
SCREENS = (
    "Account",
    "General",
    "Hotkeys",
    "Usage",
    "Mind",
    "Memory",
    "Models",
    "Skills",
    "Servers",
    "Permissions",
)


@pytest.fixture
def page(server: Served) -> Any:
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch()
        # A touch screen as well as a narrow one: `is_mobile` and `has_touch` are what make
        # `(hover: none)` and `(pointer: coarse)` true, which the chord and row-action rules
        # read.
        context = browser.new_context(viewport=PHONE, is_mobile=True, has_touch=True)
        server.sign_in(context)
        opened = context.new_page()
        opened.goto(server, wait_until="networkidle")
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def sideways(page: Any, selector: str = "") -> int:
    """How far the page, or one element in it, is wider than what shows. Zero is right."""
    return int(
        page.evaluate(
            """(selector) => {
                const el = selector ? document.querySelector(selector) : document.scrollingElement;
                return el ? el.scrollWidth - el.clientWidth : 0;
            }""",
            selector,
        )
    )


def open_rail(page: Any) -> None:
    page.get_by_role("button", name="Open menu").click()
    page.wait_for_selector(".rail-slot.sheet", timeout=5_000)


def open_settings(page: Any) -> None:
    open_rail(page)
    page.get_by_role("button", name="Settings").first.click()
    settled(page)


def settled(page: Any) -> None:
    """Settings is open and has finished arriving. The sheet scales in, so it is measured once
    what is drawn is as wide as its layout box — which is only true at full scale, however late
    the entrance started."""
    page.wait_for_selector(".sheet.settings", timeout=10_000)
    page.wait_for_function(
        """() => {
            const sheet = document.querySelector('.sheet.settings');
            const drawn = sheet.getBoundingClientRect();
            return Math.abs(drawn.width - sheet.offsetWidth) < 0.05
                && Math.abs(drawn.height - sheet.offsetHeight) < 0.05;
        }""",
        timeout=5_000,
    )


def say(page: Any, text: str) -> None:
    composer = page.locator("textarea").first
    composer.fill(text)
    composer.press("Enter")
    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=ticket-granting ticket", timeout=30_000)


class TestNothingScrollsSideways:
    def test_the_start_screen_and_a_chat(self, page: Any) -> None:
        assert sideways(page) == 0
        say(page, "Explain Kerberos")
        assert sideways(page) == 0
        assert sideways(page, ".scroll") == 0

    def test_every_settings_screen(self, page: Any) -> None:
        open_settings(page)
        for screen in SCREENS:
            page.locator(".sheet.settings").get_by_role("button", name=screen, exact=True).click()
            page.wait_for_selector(".panel:visible", timeout=5_000)
            assert sideways(page) == 0, screen
            assert sideways(page, ".panel") == 0, screen
            page.get_by_role("button", name="All settings").click()


class TestOnlyTheTranscriptScrolls:
    """The bar and the composer stay where they are; what moves is the conversation between them.

    iOS scrolled the page itself — at the end of a scroll, and when the keyboard opened — and
    took the bar and the composer with it, while the menu button, pinned to the screen, stayed
    behind: the bar came apart from its own button."""

    def test_the_menu_button_is_part_of_the_bar(self, page: Any) -> None:
        say(page, "Explain Kerberos")
        button = page.get_by_role("button", name="Open menu")
        assert button.count() == 1, "one menu button, not the bar's and a floating one"
        assert page.locator(".topbar").get_by_role("button", name="Open menu").count() == 1

    def test_the_page_itself_does_not_scroll(self, page: Any) -> None:
        say(page, "Explain Kerberos")
        page.evaluate("() => window.scrollTo(0, 500)")
        assert page.evaluate("() => window.scrollY") == 0

    def test_the_bar_and_the_composer_stay_put(self, page: Any) -> None:
        say(page, "Explain Kerberos")
        bar = page.locator(".topbar")
        composer = page.locator(".composer").first
        before = (bar.bounding_box(), composer.bounding_box())

        page.locator(".scroll").evaluate("(el) => el.scrollTo(0, 0)")
        page.mouse.wheel(0, 2000)
        page.wait_for_timeout(300)

        assert (bar.bounding_box(), composer.bounding_box()) == before
        assert before[0] is not None and before[0]["y"] == 0

    def test_the_composer_follows_the_bottom_of_what_shows(self, page: Any) -> None:
        """A keyboard takes the bottom of the screen. Narrowed to what is left, the composer is
        on the new bottom edge and the bar is still at the top."""
        say(page, "Explain Kerberos")
        page.set_viewport_size({"width": PHONE["width"], "height": 480})
        page.wait_for_timeout(300)

        composer = page.locator(".composer").first.bounding_box()
        bar = page.locator(".topbar").bounding_box()
        assert composer is not None and bar is not None
        assert bar["y"] == 0
        assert 440 <= composer["y"] + composer["height"] <= 480


class TestTheComposer:
    def test_no_chip_is_cut_off(self, page: Any) -> None:
        """Every chip but the model says all it says on a phone. The model keeps its name and
        takes the room the others gave up."""
        chips = page.locator(".composer .chip")
        cut = chips.evaluate_all(
            """(chips) => chips
                .filter((chip) => !chip.querySelector('.chevron'))
                .filter((chip) => chip.scrollWidth > chip.clientWidth)
                .map((chip) => chip.textContent.trim())"""
        )
        assert cut == []

        model = page.locator(".composer .model .chip").first
        assert model.bounding_box()["width"] >= 80

    def test_a_menu_opened_the_first_time_is_on_the_screen(self, page: Any) -> None:
        """The skill list arrives after its menu opens. The menu was placed for its empty size
        and then grew off the bottom of the screen, until it was opened a second time."""
        chip = page.get_by_role("button", name="Choose skills")
        chip.click()
        menu = page.get_by_role("menu")
        menu.locator("[role^=menuitem]").first.wait_for(timeout=10_000)
        page.wait_for_timeout(300)  # the entrance, and any second placement after it

        box = menu.bounding_box()
        anchor = chip.bounding_box()
        assert box is not None and anchor is not None
        assert box["x"] >= 0 and box["x"] + box["width"] <= PHONE["width"]
        assert box["y"] >= 0 and box["y"] + box["height"] <= PHONE["height"]
        # Above the composer it was opened from, not over it.
        assert box["y"] + box["height"] <= anchor["y"]

    def test_a_short_chip_keeps_its_full_name(self, page: Any) -> None:
        """Short to the eye, not to a screen reader."""
        assert page.get_by_role("button", name="0 servers").count() == 1


class TestSettings:
    def test_it_is_the_whole_screen_and_the_rail_is_gone(self, page: Any) -> None:
        open_settings(page)
        box = page.locator(".sheet.settings").bounding_box()
        assert (round(box["width"]), round(box["height"])) == (PHONE["width"], PHONE["height"])
        # Opened from the rail, and the rail did not stay open behind it.
        assert page.locator(".rail-slot.sheet").count() == 0

    def test_the_list_then_a_screen_then_back(self, page: Any) -> None:
        open_settings(page)
        # The list, and no screen beside it.
        assert page.locator(".sheet.settings .sidebar").is_visible()
        assert not page.locator(".sheet.settings .panel").is_visible()

        page.locator(".sheet.settings").get_by_role("button", name="Models", exact=True).click()
        page.wait_for_selector("h2:has-text('Models'), h1:has-text('Models')", timeout=5_000)
        assert not page.locator(".sheet.settings .sidebar").is_visible()
        back = page.get_by_role("button", name="All settings")
        assert back.is_visible()

        back.click()
        assert page.locator(".sheet.settings .sidebar").is_visible()
        assert not page.locator(".sheet.settings .panel").is_visible()

    def test_a_screen_asked_for_opens_on_that_screen(self, page: Any) -> None:
        """The composer's servers menu sends a person to Servers, not to a list to find it in."""
        page.get_by_role("button", name="0 servers").click()
        page.get_by_role("menuitem", name="Manage servers").click()
        settled(page)
        assert page.get_by_role("button", name="All settings").is_visible()
        panel = page.locator(".sheet.settings .panel")
        panel.get_by_role("button", name="New server").wait_for(timeout=10_000)


class TestMemory:
    def test_every_switch_is_inside_its_card(self, page: Any) -> None:
        """A row held the key, its badges, the cost, a word and the switch on one line, and the
        switch ran off the edge of its card. Written as files because no route makes a memory:
        she does, and a person edits one."""
        # The signed-in admin's own memories (ADR 28); a top-level `memories/` is nobody's now.
        owner = str(CoreSettings().owner_id)
        memories = Path(os.environ["HERA_HOME"]) / "users" / owner / "memories"
        memories.mkdir(parents=True, exist_ok=True)
        for key, scope in (("visit-family-december-2026", "global"), ("short-answers", "chat")):
            memories.joinpath(f"{key}.md").write_text(
                f"---\ndescription: A line about {key}.\nscope: {scope}\nsource: auto\n"
                f"enabled: true\n---\n\nWhat she knows about {key}.\n",
                encoding="utf-8",
            )

        open_settings(page)
        page.locator(".sheet.settings").get_by_role("button", name="Memory", exact=True).click()
        page.wait_for_selector(".item", timeout=10_000)
        outside = page.locator(".item").evaluate_all(
            """(items) => items.flatMap((item) => {
                const card = item.getBoundingClientRect();
                return [...item.querySelectorAll('button, [role="switch"], input')]
                    .map((el) => el.getBoundingClientRect())
                    .filter((box) => box.width && (box.right > card.right || box.left < card.left))
                    .map(() => item.querySelector('.key')?.textContent);
            })"""
        )
        assert outside == []


class TestTouch:
    def test_the_rail_draws_no_chords(self, page: Any) -> None:
        open_rail(page)
        assert page.locator(".rail-slot kbd").count() > 0, "the rail lists chords on a desktop"
        assert page.locator(".rail-slot kbd:visible").count() == 0

    def test_a_rows_menu_is_there_without_a_hover(self, page: Any) -> None:
        say(page, "Explain Kerberos")
        open_rail(page)
        action = page.locator(".rail-slot .action").first
        assert float(action.evaluate("(el) => getComputedStyle(el).opacity")) == 1

    def test_no_field_is_small_enough_to_zoom_into(self, page: Any) -> None:
        """iOS zooms into a field under 16px on focus and stays zoomed."""
        open_settings(page)
        page.locator(".sheet.settings").get_by_role("button", name="Account", exact=True).click()
        # A file picker is a hidden input behind a button, and nobody types into it.
        fields = "input:not([type='file']):visible, textarea:visible"
        sizes = page.locator(fields).evaluate_all(
            "(fields) => fields.map((f) => parseFloat(getComputedStyle(f).fontSize))"
        )
        assert sizes, "the account screen has fields"
        assert min(sizes) >= 16, sizes

"""From a keystroke to a rendered emotion card.

The one test that proves the whole thing is joined up: SvelteKit built, served by FastAPI,
streaming Server-Sent Events out of the turn orchestrator, reduced in the browser into a
message. Everything real except the model.
"""

from __future__ import annotations

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
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        opened = context.new_page()
        opened.goto(server, wait_until="networkidle")
        try:
            yield opened
        finally:
            context.close()
            browser.close()


def test_the_start_screen_greets_and_focuses_the_composer(page: Any) -> None:
    """Mark, greeting, composer, nothing else — and nothing to click before typing."""
    assert (
        page.locator("text=Good").first.is_visible() or page.locator(".display").first.is_visible()
    )
    assert page.locator("textarea").first.is_visible()


def test_a_message_streams_back_and_survives_a_reload(page: Any) -> None:
    composer = page.locator("textarea").first
    composer.fill("Explain Kerberos")
    composer.press("Enter")

    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=ticket-granting ticket", timeout=30_000)

    # An emotion renders as a card, inline, where she called it (ADR 3).
    page.wait_for_selector("text=curious", timeout=15_000)

    # The thinking channel is a gutter row, never mixed into the prose. Asserted against the
    # prose rather than against the whole page: the gutter previews the tail of a block while
    # it is still being written, so "the words are nowhere on screen" stopped being the same
    # claim as "the words are not in her answer" — and it is the second one this rule is about.
    reasoning = "They want the short version"
    assert page.locator(f".prose:has-text('{reasoning}')").count() == 0

    # Where it does live: a row in the gutter that opens onto it. The preview is gone by now —
    # it belongs to the block still being written, and this turn has finished.
    assert page.locator("article.hers .tail").count() == 0
    page.locator("article.hers .row .head", has_text="thought").first.click()
    page.wait_for_selector(f"article.hers .body:has-text('{reasoning}')", timeout=5_000)

    url = page.url
    page.reload(wait_until="networkidle")

    # The server render is authoritative: the reload shows exactly what was streamed.
    page.wait_for_selector("text=ticket-granting ticket", timeout=15_000)
    page.wait_for_selector("text=curious", timeout=15_000)
    assert page.url == url


def test_her_prose_is_typeset_rather_than_dumped(page: Any) -> None:
    """Markdown and TeX reach the screen as structure, not as their own source (ADR 11).

    The `---` is the case worth a browser: Markdown's setext form would make it promote the
    line above it to a heading, so the commonest way a model separates two thoughts would
    silently shout the sentence it had just finished.
    """
    composer = page.locator("textarea").first
    composer.fill("Explain Kerberos")
    composer.press("Enter")

    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector(".prose li", timeout=30_000)

    assert page.locator(".prose li").count() >= 2
    assert page.locator(".prose hr").count() == 1
    assert page.locator(".prose h2").count() == 0
    assert page.locator(".prose .katex").count() >= 1

    # And nothing of the notation is left lying on the screen.
    assert page.locator("text=\\(t_0").count() == 0


def test_a_question_is_edited_and_an_answer_tried_again(page: Any) -> None:
    """Both are the same request — the conversation goes forward from here differently — and
    both delete what came after, in the browser as well as on the server."""
    composer = page.locator("textarea").first
    composer.fill("Explain Kerberos")
    composer.press("Enter")

    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=ticket-granting ticket", timeout=30_000)
    page.wait_for_selector("text=Ask me for the detail", timeout=30_000)

    page.locator(".mine").first.hover()
    page.get_by_role("button", name="Edit").click()
    field = page.locator(".editor textarea")
    field.fill("Explain Kerberos in one line")
    page.get_by_role("button", name="Ask again").click()

    page.wait_for_selector("text=Shorter: one ticket buys the rest.", timeout=30_000)
    # The old question and the answer to it are gone, not hidden.
    assert page.locator("text=Explain Kerberos in one line").count() >= 1
    assert page.locator("text=ticket-granting ticket").count() == 0

    page.locator(".hers").last.hover()
    page.get_by_role("button", name="Try again").click()

    page.wait_for_selector("text=Once more, then.", timeout=30_000)
    assert page.locator("text=Shorter: one ticket buys the rest.").count() == 0
    # The question it was answering stayed exactly where it was.
    assert page.locator("text=Explain Kerberos in one line").count() >= 1


def test_a_chat_is_renamed_and_deleted_from_the_rail(page: Any) -> None:
    """The ⋯ menu, which is the only way to correct a title she chose or to throw a
    conversation away. Renaming is an input where the title was; deleting asks first."""
    composer = page.locator("textarea").first
    composer.fill("Explain Kerberos")
    composer.press("Enter")
    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("nav.rail li.item", timeout=15_000)

    page.locator("nav.rail button.more").first.click()
    page.get_by_role("menuitem", name="Rename").click()

    field = page.locator("input.rename")
    field.fill("Tickets, not passwords")
    field.press("Enter")

    page.wait_for_selector("text=Tickets, not passwords", timeout=10_000)
    page.reload(wait_until="networkidle")
    # A title typed by hand sticks: she only ever names a chat that has no name.
    page.wait_for_selector("text=Tickets, not passwords", timeout=15_000)

    page.locator("nav.rail button.more").first.click()
    page.get_by_role("menuitem", name="Delete").click()
    assert page.locator("text=Delete this chat?").count() == 1
    page.get_by_role("menuitem", name="Delete").click()

    # The conversation on screen went with it, so the route goes back to the start.
    page.wait_for_url(lambda url: "/chat/" not in url, timeout=10_000)
    assert page.locator("nav.rail li.item").count() == 0


def test_the_composer_says_what_she_runs_on(page: Any) -> None:
    """The model is a control beside send rather than a setting two screens away, and the
    Enter hint gets out of the way as soon as there is something to send."""
    assert page.locator("label.model select").first.input_value() != ""

    hint = page.locator("span.hint").first
    assert "gone" not in (hint.get_attribute("class") or "")

    page.locator("textarea").first.fill("Explain Kerberos")
    assert "gone" in (page.locator("span.hint").first.get_attribute("class") or "")


def test_a_skill_is_switched_on_for_one_chat(page: Any) -> None:
    """ADR 5 says the model is never asked which skill applies. This is where a person answers
    instead — and the answer sticks to the conversation, not to the profile."""
    composer = page.locator("textarea").first
    composer.fill("Explain Kerberos")
    composer.press("Enter")
    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=ticket-granting ticket", timeout=30_000)

    page.locator("button.context").click()
    page.wait_for_selector("[role=dialog]", timeout=10_000)
    page.locator(".entry", has_text="tdd").click()
    page.keyboard.press("Escape")

    page.wait_for_selector("button.context:has-text('1 skill')", timeout=10_000)

    page.reload(wait_until="networkidle")
    # Stored on the chat, so it survives the reload that everything else here survives.
    page.wait_for_selector("button.context:has-text('1 skill')", timeout=15_000)


def test_settings_holds_what_changes_her_behaviour(page: Any) -> None:
    """Models first, because nothing works until she is pointed at one; then the two lists a
    person comes back to. Dreaming is listed and disabled rather than hidden — a v0.2 feature
    you can see coming is a promise, and one you cannot is a surprise."""
    page.get_by_role("button", name="Settings").click()
    page.wait_for_selector("[role=dialog]", timeout=10_000)

    nav = page.locator("[role=dialog] nav.tabs button")
    assert nav.all_inner_texts()[:4] == ["Models", "Skills", "Servers", "Permissions"]
    assert "Dreaming" in nav.last.inner_text()

    # The endpoint is registered and editable, which is the whole point of this screen.
    page.wait_for_selector("text=Base URL", timeout=10_000)

    page.keyboard.press("Escape")
    page.wait_for_selector("[role=dialog]", state="detached", timeout=10_000)


def test_the_profile_card_holds_everything_that_is_not_about_her(page: Any) -> None:
    """Appearance and where your data lives are not model behaviour, and mixing the two is how
    a person ends up scrolling past six model fields to find a light-mode toggle."""
    page.locator("button.card").click()
    page.wait_for_selector("[role=dialog]", timeout=10_000)

    menu = page.locator("[role=dialog]")
    assert "APPEARANCE" in menu.inner_text().upper()
    assert "ABOUT" in menu.inner_text().upper()

    page.keyboard.press("Escape")
    page.wait_for_selector("[role=dialog]", state="detached", timeout=10_000)


def test_a_file_can_be_attached_and_is_drawn_as_a_chip(page: Any, tmp_path: Any) -> None:
    """The file reaches the model inlined and the browser draws a chip from a field — neither
    side parses the other's rendering."""
    note = tmp_path / "notes.md"
    note.write_text("Slide 14 contradicts slide 9.")

    page.set_input_files("input[type=file]", str(note))
    page.wait_for_selector("text=notes.md", timeout=10_000)

    composer = page.locator("textarea").first
    composer.fill("What is wrong with these?")
    composer.press("Enter")

    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=ticket-granting ticket", timeout=30_000)

    # The chip survives, and the file's contents are not pasted into the bubble.
    assert page.locator("li:has-text('notes.md')").count() >= 1
    assert page.locator("text=Slide 14 contradicts slide 9.").count() == 0

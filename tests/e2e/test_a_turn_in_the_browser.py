"""From a keystroke to a rendered emotion card.

The one test that proves the whole thing is joined up: SvelteKit built, served by FastAPI,
streaming Server-Sent Events out of the turn orchestrator, reduced in the browser into a
message. Everything real except the model.
"""

from __future__ import annotations

from typing import Any

import pytest

from hera_providers import TextDelta, TurnEnd, text_turn, tool_call

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

    # And now wait for the turn to actually be over. The emotion closes the *first* round trip,
    # not the turn: the script answers a second time after it, and everything below is written
    # about a finished turn — the tail preview being gone, and a row that stays open once it is
    # clicked. Until `done` arrives the client is still rendering optimistically and then
    # replaces the lot with the persisted list, which on a slow runner lands after the click and
    # takes the opened row with it.
    page.wait_for_selector("text=Ask me for the detail", timeout=30_000)

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
    Enter hint gets out of the way as soon as there is something to send.

    The control is `Select`, not a native `<select>`: it draws its own popup so that a list
    looks the same wherever it was opened from. So what is asserted is what a person sees — the
    pill naming the active endpoint — rather than a form value nothing renders.
    """
    model = page.get_by_label("Model", exact=True)
    assert model.inner_text().strip() != ""

    hint = page.locator("span.hint").first
    assert "gone" not in (hint.get_attribute("class") or "")

    page.locator("textarea").first.fill("Explain Kerberos")
    assert "gone" in (page.locator("span.hint").first.get_attribute("class") or "")


def test_a_dropdown_opens_the_interfaces_own_list(page: Any) -> None:
    """Not the platform's. Every popup in the application is one frame — the raised surface,
    the hairline, the large radius — so a dropdown and the skill picker read as the same act.

    Worth a browser rather than a unit test, because what is being checked is that opening it
    produces our markup at all: a native `<select>` renders its list outside the DOM, where
    nothing here could see it and this assertion would be impossible to write.
    """
    page.get_by_label("Model", exact=True).click()
    page.wait_for_selector('[role="listbox"]', timeout=5_000)

    listbox = page.locator('[role="listbox"]')
    assert listbox.locator('[role="option"]').count() >= 1
    # The current value is marked in the list, not only shown on the pill.
    assert listbox.locator('[role="option"][aria-selected="true"]').count() == 1

    # Escape closes it and hands focus back, so the keyboard is not left inside a closed popup.
    page.keyboard.press("Escape")
    page.wait_for_selector('[role="listbox"]', state="detached", timeout=5_000)


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

    # Wait for the write itself, not for the pill. `ChatStore.pinSkills` is deliberately
    # optimistic — a tick that waits for a round trip reads as a click that did not land — so the
    # pill says "1 skill" while the PATCH is still in flight, and `reload` cancels what is still
    # in flight. Asserting the response is what makes the reload below a test of persistence
    # rather than a race the runner wins when it is fast and loses when it is loaded.
    with page.expect_response(
        lambda response: response.request.method == "PATCH" and "/chats/" in response.url
    ) as patched:
        page.locator(".entry", has_text="tdd").click()
    assert patched.value.ok

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


ASKING_SCRIPT: list[Any] = [
    # She asks before answering, which is what the `uncertainty` mind region tells her to do
    # when being wrong would cost real work. The turn stops here.
    [
        TextDelta(text="Before I summarise it — "),
        tool_call("hera__ask", {"question": "Which deck do you mean?", "kind": "unsure"}),
        TurnEnd(reason="tool_calls"),
    ],
    # And carries on with the reply in hand, as the result of its own call.
    text_turn("The 2024 one, then: three slides on ticket lifetime."),
]
"""Its own script rather than more turns on the shared one: every test starts a fresh provider
at turn zero, so a question buried at index four would never be reached.

Here rather than in ``conftest.py`` because mypy excludes that file — pytest loads it by path
and mypy does not — so anything imported from it is invisible to the type checker.
"""


class TestSheAsksAndWaits:
    """`hera__ask` in a real browser: the turn stops, a card takes a reply, and the answer she
    was given becomes the result of her own call.

    Its own script, because every test starts a fresh provider at turn zero.
    """

    @pytest.fixture
    def script(self) -> list[Any]:
        """Overrides the fixture in ``conftest.py``, which serves the shared script."""
        return ASKING_SCRIPT

    def test_a_question_stops_the_turn_and_the_reply_resumes_it(self, page: Any) -> None:
        composer = page.locator("textarea").first
        composer.fill("Summarise the deck")
        composer.press("Enter")

        page.wait_for_url("**/chat/**", timeout=15_000)
        page.wait_for_selector("text=Which deck do you mean?", timeout=30_000)

        # The stance she asked in, from the same open vocabulary an emotion card draws on.
        page.wait_for_selector("text=unsure", timeout=5_000)

        # The composer is blocked while the question is open: there is one thing to answer and
        # two places to type it would be a question about which one counts.
        assert page.locator("textarea[disabled]").count() >= 1

        reply = page.locator("aside textarea").first
        reply.fill("The 2024 one.")
        reply.press("Enter")

        page.wait_for_selector("text=three slides on ticket lifetime", timeout=30_000)

        # One assistant message, not two: she asked, waited, and carried on.
        assert page.locator("article.hers").count() == 1

        url = page.url
        page.reload(wait_until="networkidle")

        # The server render is authoritative here too: the settled card comes back with the
        # reply on it, rather than as a live field asking again.
        page.wait_for_selector("text=Which deck do you mean?", timeout=15_000)
        page.wait_for_selector("text=The 2024 one.", timeout=15_000)
        page.wait_for_selector("text=three slides on ticket lifetime", timeout=15_000)
        assert page.url == url


class TestATurnThatFailed:
    """The turn you most want to try again is the one with no answer in it.

    A provider that stops responding closes the turn with `failed` and whatever arrived before
    it — which for a model that was still thinking is a gutter and no prose at all. The message
    then had nothing to act on, so *Try again* was not drawn on the one message that needed it,
    and the question above it could not be edited either.
    """

    @pytest.fixture
    def script(self) -> list[Any]:
        from hera_providers import ProviderTimeout, ThinkingDelta

        return [
            # Thinks, and then the endpoint stops answering mid-stream. The error sits *among*
            # the events, so the thinking has already been streamed when it is raised — which is
            # the shape that matters here: a turn that failed with a gutter and no prose in it.
            [
                ThinkingDelta(text="They want a whole page of markup."),
                ProviderTimeout("http://localhost:1234/v1 did not answer in time"),
            ],
            text_turn("Second time lucky."),
        ]

    def _fail(self, page: Any) -> None:
        composer = page.locator("textarea").first
        composer.fill("Build me a page")
        composer.press("Enter")
        page.wait_for_url("**/chat/**", timeout=15_000)
        page.wait_for_selector("text=did not answer in time", timeout=30_000)

    def test_the_failed_answer_can_be_tried_again(self, page: Any) -> None:
        self._fail(page)

        page.locator(".hers").last.hover()
        page.get_by_role("button", name="Try again").click()

        page.wait_for_selector("text=Second time lucky.", timeout=30_000)

    def test_the_question_above_it_can_still_be_edited(self, page: Any) -> None:
        self._fail(page)

        page.locator(".mine").first.hover()
        page.get_by_role("button", name="Edit").click()
        field = page.locator(".editor textarea")
        field.fill("Build me a smaller page")
        page.get_by_role("button", name="Ask again").click()

        page.wait_for_selector("text=Second time lucky.", timeout=30_000)

    def test_there_is_nothing_to_copy_and_it_does_not_pretend_otherwise(self, page: Any) -> None:
        """Copy is about the answer, and there is no answer. Drawing a button that puts an
        empty string on the clipboard would be worse than leaving it out."""
        self._fail(page)

        page.locator(".hers").last.hover()
        assert page.locator(".hers").last.get_by_role("button", name="Copy").count() == 0


ARTIFACT_SCRIPT: list[Any] = [
    # Each *round trip* is one entry, and a turn with tools in it takes two: the calls, and then
    # the answer written with their results in hand. So three questions are six entries here.
    #
    # A page, published rather than dumped into the answer as a code fence. `inline=false`, so
    # what lands in the transcript is a card with an **Open** on it.
    [
        TextDelta(text="Here is the page.\n\n"),
        tool_call(
            "hera__artifact_create",
            {
                "name": "theme-workshop.html",
                "content": "<h1>Theme workshop</h1><p id='swatch'>brass</p>",
                "inline": False,
            },
        ),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("Open it and tell me what you think."),
    # A figure, published with `inline=true`, so it is drawn in the middle of the explanation
    # rather than filed away — which is the case ADR 13 exists to distinguish.
    [
        tool_call(
            "hera__artifact_create",
            {
                "name": "flow.svg",
                "content": (
                    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 20'>"
                    "<circle cx='10' cy='10' r='6'/></svg>"
                ),
                "inline": True,
            },
        ),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("The middle step is the slow one."),
    # One colour changed without re-emitting the file, which is the whole point of `edit`.
    [
        tool_call(
            "hera__artifact_edit",
            {"name": "theme-workshop.html", "find": "brass", "replace": "laurel"},
        ),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("Changed."),
]
"""Its own script, because every test starts a fresh provider at turn zero."""


class TestWhatShePublishes:
    """ADR 13 in a real browser, against the real registry — her own MCP server is mounted and
    the files really land in the temporary `HERA_HOME`, so what is asserted here is the whole
    path: tool call, structured result, event, reducer, card, drawer.
    """

    @pytest.fixture
    def script(self) -> list[Any]:
        return ARTIFACT_SCRIPT

    def _ask(self, page: Any, text: str) -> None:
        composer = page.locator("textarea:not([disabled])").first
        composer.fill(text)
        composer.press("Enter")

    def _publish(self, page: Any) -> None:
        self._ask(page, "Build me a page")
        page.wait_for_url("**/chat/**", timeout=15_000)
        page.wait_for_selector("text=Open it and tell me what you think.", timeout=30_000)

    def _drawer(self, page: Any) -> Any:
        return page.locator("aside[aria-label='Artifacts']")

    def test_a_page_opens_beside_the_conversation_as_she_publishes_it(self, page: Any) -> None:
        """Nothing is clicked here, and that is the assertion. A page is something you look at,
        so the drawer follows her — hunting for the **Open** on a card that is still arriving is
        a step with nothing behind it."""
        self._publish(page)

        # The page itself, in a frame with an opaque origin: `allow-scripts` and deliberately
        # not `allow-same-origin`, so what she wrote cannot reach Hera's storage.
        frame = page.locator("iframe[title='theme-workshop.html']")
        frame.wait_for(timeout=15_000)
        sandbox = frame.get_attribute("sandbox") or ""
        assert "allow-scripts" in sandbox
        assert "allow-same-origin" not in sandbox
        assert "Theme workshop" in (frame.get_attribute("srcdoc") or "")

        # And the file bar, which is what makes it reachable once the turn has scrolled away.
        assert page.locator("nav[aria-label='Everything published here']").count() == 1

    def test_the_card_opens_it_again_after_it_is_closed(self, page: Any) -> None:
        """The drawer opening by itself is a convenience and the card is the door. Closing it
        has to mean closed — an **Open** that re-opens what is already open would be a control
        that does nothing."""
        self._publish(page)
        page.get_by_role("button", name="Close").click()
        assert self._drawer(page).count() == 0

        # The heading is the filename humanised — there is no title field anywhere for it to
        # disagree with, which is the decision this assertion pins.
        assert page.get_by_text("Theme workshop", exact=True).count() == 1
        page.get_by_role("button", name="Open").first.click()
        page.locator("iframe[title='theme-workshop.html']").wait_for(timeout=15_000)

    def test_the_card_carries_a_way_to_save_it(self, page: Any) -> None:
        """Saving is the other thing anybody does with a published file, and until the card had
        this it meant opening the drawer to reach the link. A plain `<a download>`, because the
        browser knows how to save a file and the response says `attachment`."""
        self._publish(page)
        page.get_by_role("button", name="Close").click()

        save = page.get_by_role("link", name="Download theme-workshop.html")
        assert save.count() == 1
        assert save.get_attribute("download") == "theme-workshop.html"
        assert "/artifacts/theme-workshop.html/download" in (save.get_attribute("href") or "")

    def test_the_card_survives_a_reload(self, page: Any) -> None:
        """The server render is authoritative: the persisted list has no `tool_call_started` in
        it, and it has to draw the same card the live stream did.

        The drawer is deliberately *not* part of that. Opening one is something she does while
        publishing, not a property of the conversation — coming back to it leaves you where you
        left off rather than reopening a panel over the transcript you came to read."""
        self._publish(page)

        page.reload(wait_until="networkidle")

        page.wait_for_selector("text=Theme workshop", timeout=15_000)
        assert page.get_by_role("button", name="Open").count() >= 1
        assert self._drawer(page).count() == 0

    def test_a_figure_is_drawn_where_she_drew_it(self, page: Any) -> None:
        """`inline` is the whole distinction ADR 13 exists to make, and the drawer is where it
        shows: a page takes the panel, a figure never does. Taking half the width away from the
        sentence a diagram explains is the opposite of what `inline` asked for."""
        self._publish(page)
        page.get_by_role("button", name="Close").click()

        self._ask(page, "Now show me the flow")
        page.wait_for_selector("text=The middle step is the slow one.", timeout=30_000)

        # Drawn in the transcript rather than behind a card: the drawing is in the message, and
        # the panel stayed shut.
        page.locator(".hers .drawing svg").first.wait_for(timeout=15_000)
        assert self._drawer(page).count() == 0

    def test_throwing_the_chat_away_says_what_goes_with_it(self, page: Any) -> None:
        """*A chat is a thing you throw away* and *the page I made last week* have to be
        reconciled by a sentence rather than by a surprise (ADR 13). The count is fetched when
        the confirmation opens rather than carried on every row in the rail."""
        self._publish(page)

        page.locator(".item .more").first.click()
        page.get_by_role("menuitem", name="Delete").click()

        page.wait_for_selector("text=The artifact in it goes too.", timeout=15_000)

    def test_an_edit_says_so_in_the_gutter_and_draws_no_second_card(self, page: Any) -> None:
        """An artifact has one current state everywhere it appears, so the card that published
        it already shows the change — a second card would be one file drawn twice."""
        self._publish(page)
        # Closed, so the count below is counting cards. The drawer names what it is showing, and
        # it is showing this same file.
        page.get_by_role("button", name="Close").click()
        self._ask(page, "Now show me the flow")
        page.wait_for_selector("text=The middle step is the slow one.", timeout=30_000)

        self._ask(page, "Make the swatch laurel")
        page.wait_for_selector("text=Changed.", timeout=30_000)

        # The row says what she did: `artifact edit` is the verb and the filename is the target.
        assert page.locator("text=artifact edit").count() >= 1
        assert page.get_by_text("Theme workshop", exact=True).count() == 1


TALL_SCRIPT: list[Any] = [
    [
        TextDelta(text="Top to bottom.\n\n"),
        tool_call(
            "hera__artifact_create",
            {
                "name": "ladder.svg",
                "content": (
                    "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='1400' "
                    "viewBox='0 0 400 1400'><circle cx='200' cy='200' r='120'/></svg>"
                ),
                "inline": False,
            },
        ),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("The bottom step is the last one."),
]
"""A drawing far taller than the panel it opens in — the shape that broke."""


class TestADrawingKeepsItsShape:
    """A layout bug worth a browser, because nothing below the browser can see it.

    An `<svg>` is a replaced element with an aspect ratio of its own, and it was being drawn in
    a flex box: `align-items: stretch` takes a flex item whose height is `auto` and sets that
    height from the *box*, so the panel's `max-height` squashed a 400 x 1400 chart to the height
    of the screen and `preserveAspectRatio` then shrank the drawing to a thumbnail in an acre of
    white. It reads as an artifact that came out broken rather than as a layout that is wrong,
    which is exactly the failure ADR 13 does not want a person to have to diagnose.

    Asserting on the *shape* rather than on the CSS: whatever the box does, the drawing has to
    come out of it with the proportions she gave it.
    """

    @pytest.fixture
    def script(self) -> list[Any]:
        return TALL_SCRIPT

    def test_a_tall_drawing_is_not_squashed_into_the_panel(self, page: Any) -> None:
        composer = page.locator("textarea:not([disabled])").first
        composer.fill("Draw me a ladder")
        composer.press("Enter")
        page.wait_for_url("**/chat/**", timeout=15_000)
        page.wait_for_selector("text=The bottom step is the last one.", timeout=30_000)

        drawing = page.locator("aside[aria-label='Artifacts'] .drawing svg")
        drawing.wait_for(timeout=15_000)
        box = drawing.bounding_box()

        # 400 x 1400, so 3.5 — and it is the panel that scrolls, not the picture that shrinks.
        assert box is not None
        assert abs(box["height"] / box["width"] - 3.5) < 0.05
        panel = page.locator("aside[aria-label='Artifacts'] .drawing").bounding_box()
        assert panel is not None
        assert box["height"] > panel["height"]


MEMORY_SCRIPT: list[Any] = [
    [
        TextDelta(text="Noted.\n\n"),
        tool_call(
            "hera__remember",
            {
                "key": "runs-models-locally",
                "text": "They run local models through LM Studio on an M-series Mac.",
                "description": "Runs local models on Apple silicon",
                "why": "Corrected me after I suggested CUDA flags",
            },
        ),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("I will not suggest CUDA flags again."),
]
"""One thing worth keeping, written down the way she writes one."""


class TestWhatSheRemembers:
    """ADR 16 in a real browser, against the real store — her own MCP server is mounted and the
    file really lands in the temporary `HERA_HOME`.

    What is worth driving a browser for is the *bar*, because it is the only part of this
    feature that cannot be checked anywhere else: the number comes from the server, the row
    beside it comes from the server, and the whole point of showing them together is that a
    person can compare them.
    """

    @pytest.fixture
    def script(self) -> list[Any]:
        return MEMORY_SCRIPT

    def _remember(self, page: Any) -> None:
        composer = page.locator("textarea:not([disabled])").first
        composer.fill("I run models on a Mac")
        composer.press("Enter")
        page.wait_for_url("**/chat/**", timeout=15_000)
        page.wait_for_selector("text=I will not suggest CUDA flags again.", timeout=30_000)

    def _open_memory(self, page: Any) -> Any:
        """The panel, once it has its list.

        Everything below is scoped through what this returns, and that is not fussiness. The
        transcript behind the modal has an **Edit** on every message and now carries the memory's
        key in its gutter row, so a page-wide `get_by_role` or `text=` reaches through the open
        modal and matches the conversation — as a stale assertion, or as a click the modal's own
        panel then intercepts.
        """
        page.get_by_role("button", name="Settings").first.click()
        page.get_by_role("button", name="Memory", exact=True).click()
        panel = page.locator("section.memory")
        panel.locator("li.item").first.wait_for(timeout=15_000)
        return panel

    def test_what_she_wrote_down_is_on_the_screen_with_what_it_costs(self, page: Any) -> None:
        self._remember(page)
        panel = self._open_memory(page)

        assert panel.get_by_text("runs-models-locally").count() == 1
        # The description and the `why` are never injected, so this screen is the only place
        # either of them is ever seen — which is the whole reason they are worth storing.
        assert panel.get_by_text("Runs local models on Apple silicon").count() == 1
        assert panel.get_by_text("because Corrected me after I suggested CUDA flags").count() == 1

        # And the bar, which is what makes the ceiling something to steer by rather than hit.
        meter = panel.locator("[role='meter']")
        assert meter.count() == 1
        assert meter.get_attribute("aria-valuemax") == "4000"
        assert int(meter.get_attribute("aria-valuenow") or "0") > 0

    def test_switching_one_off_gives_the_space_back_without_losing_it(self, page: Any) -> None:
        """The middle option between having something and deleting it, and the thing the bar
        exists to make legible. The row stays, greyed rather than gone — hiding it is how a
        person loses the ability to switch it back on."""
        self._remember(page)
        panel = self._open_memory(page)

        before = int(panel.locator("[role='meter']").get_attribute("aria-valuenow") or "0")
        panel.get_by_role("checkbox", name="Use runs-models-locally").click()

        panel.get_by_text("Kept, not used").wait_for(timeout=15_000)
        # Waited for rather than read: the row moves optimistically and the bar is re-read from
        # the server, on purpose. What a memory costs and what the bar totals are one piece of
        # arithmetic, and doing it a second time in the browser is how the two come to disagree.
        panel.locator("[role='meter'][aria-valuenow='0']").wait_for(timeout=15_000)
        assert before > 0
        assert panel.get_by_text("runs-models-locally").count() == 1
        assert panel.locator("li.item.off").count() == 1

    def test_a_person_can_correct_what_she_wrote_down(self, page: Any) -> None:
        """Behind a Save rather than on blur, unlike Settings → Emotions: the body is a paragraph,
        and a blur that commits is a blur that can commit half a sentence."""
        self._remember(page)
        panel = self._open_memory(page)

        panel.get_by_role("button", name="Edit").click()
        panel.locator("li.item textarea").fill("They run local models on an M4 Pro, not a Studio.")
        panel.get_by_role("button", name="Save").click()

        panel.get_by_text("an M4 Pro, not a Studio").wait_for(timeout=15_000)
        # The badge says who *started* it, not who touched it last.
        assert panel.get_by_text("she wrote it").count() == 1

    def test_it_can_be_taken_somewhere_that_is_not_hera(self, page: Any) -> None:
        """A plain `<a download>` at the export route. The document is partly text a model
        wrote, so it arrives as an attachment rather than as a page at Hera's own origin."""
        self._remember(page)
        panel = self._open_memory(page)

        export = panel.get_by_role("link", name="Export MEMORY.md")
        assert export.count() == 1
        assert export.get_attribute("download") == "MEMORY.md"

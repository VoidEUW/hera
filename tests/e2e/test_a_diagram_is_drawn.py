"""A diagram comes out as a picture, in the sentence it belongs to.

[Issue #73](https://github.com/VoidEUW/hera/issues/73). `.mmd` was a real artifact kind with no
renderer behind it since ADR 13 -- v0.2.0 shipped the source view and deferred the drawing,
because mermaid is two to three megabytes of browser dependency -- and the reason it is worth
having is not the file kind: a model that can describe a flow chart in six lines of mermaid very
often cannot write the same picture as SVG path data.

`hera__diagram_create` is its own tool for the reason this file drives twice. Where a diagram
lands is not a judgment a model should be making call by call -- it is the same conclusion ADR 5
reached about skills, that a mechanism which only works when the model volunteers is not a
mechanism -- so the tool takes mermaid and a name, decides the extension itself, and draws in the
flow unless the call explicitly says `beside`.

Driven in a browser because nothing below one can see it: mermaid lays a diagram out by measuring
its own text, so `getBBox` has to be real.

Two seams can break quietly and both are pinned below. The drawing goes through the same svg-only
sanitiser an `.svg` artifact goes through, and mermaid's *default* label is a `<foreignObject>`
full of XHTML -- which that profile strips, correctly and catastrophically: the boxes and the
arrows arrive with no text in them at all. `$lib/mermaid` turns `htmlLabels` off so a label is a
real `<text>` element instead, and the assertion here is on the labels, because a diagram whose
words are gone still looks like a diagram from any distance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hera_providers import TextDelta, TurnEnd, text_turn, tool_call

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

HANDSHAKE = "flowchart TD\n  A[Client hello] --> B[Server hello]\n  B --> C[Finished]\n"

# No extension and nothing about placement, which is the call this tool is built for: both are
# decided by the server, and a call that says neither is the ordinary one.
DIAGRAM_SCRIPT: list[Any] = [
    [
        TextDelta(text="Here is the handshake.\n\n"),
        tool_call("hera__diagram_create", {"name": "handshake", "mermaid": HANDSHAKE}),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("Three messages, and the last one is the cheap one."),
]

# The same diagram, asked for beside the conversation. The only say the model gets over where it
# lands, and it has to be an explicit one.
BESIDE_SCRIPT: list[Any] = [
    [
        TextDelta(text="Here is the handshake.\n\n"),
        tool_call(
            "hera__diagram_create",
            {"name": "handshake", "mermaid": HANDSHAKE, "beside": True},
        ),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("Three messages, and the last one is the cheap one."),
]

# A diagram, and then a great many words after it. Each one is a fragment on the wire and a
# render of the whole transcript, which is the condition a card already on screen has to survive.
TALKATIVE_SCRIPT: list[Any] = [
    [
        TextDelta(text="Here is the handshake.\n\n"),
        tool_call("hera__diagram_create", {"name": "handshake", "mermaid": HANDSHAKE}),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn(*(f"word{n} " for n in range(30)), "THE LAST WORD."),
]

# Not a diagram at all, rather than a flow chart with a typo in it: mermaid decides what kind of
# diagram it is from the first word, so this is the one failure that cannot start passing because
# a later mermaid grew a tolerance for it.
BROKEN_SCRIPT: list[Any] = [
    [
        TextDelta(text="Here is the handshake.\n\n"),
        tool_call(
            "hera__diagram_create",
            {"name": "handshake", "mermaid": "steps: hello, hello back, done\n"},
        ),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("Three messages, and the last one is the cheap one."),
]


# Frontmatter is ordinary mermaid, not an exotic payload -- and `htmlLabels: true` is the one
# setting that would put the labels back into a `<foreignObject>` for the sanitiser to strip.
OVERRIDE = (
    "---\nconfig:\n  htmlLabels: true\n---\n"
    "flowchart TD\n  A[Client hello] --> B[Server hello]\n  B --> C[Finished]\n"
)

OVERRIDE_SCRIPT: list[Any] = [
    [
        TextDelta(text="Here is the handshake.\n\n"),
        tool_call("hera__diagram_create", {"name": "handshake", "mermaid": OVERRIDE}),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("Three messages, and the last one is the cheap one."),
]


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


def publish(page: Any) -> None:
    composer = page.locator("textarea:not([disabled])").first
    composer.fill("Draw me the handshake")
    composer.press("Enter")
    page.wait_for_url("**/chat/**", timeout=15_000)
    page.wait_for_selector("text=the last one is the cheap one", timeout=30_000)


class TestADiagramIsDrawn:
    @pytest.fixture
    def script(self) -> list[Any]:
        return DIAGRAM_SCRIPT

    def test_it_is_drawn_with_its_labels_on_it(self, page: Any) -> None:
        """The whole of issue #73 in one assertion, and the labels are the half that is easy to
        lose: `htmlLabels` off is what lets a diagram and the sanitiser want the same thing.

        The renderer is fetched on demand, so this waits longer than a drawing she wrote herself
        would need -- that wait is the feature, not a slow test."""
        publish(page)

        drawing = page.locator(".hers .drawing svg").first
        drawing.wait_for(timeout=30_000)

        labels = drawing.locator("text").all_text_contents()
        joined = " ".join(labels)
        assert "Client hello" in joined
        assert "Server hello" in joined
        assert "Finished" in joined

        # Nothing that the svg profile would have had to strip, and nothing it did strip: a
        # `<foreignObject>` here would mean the labels above arrived by luck.
        assert drawing.locator("foreignObject").count() == 0

        # And it really is drawn rather than shown as text -- the source view is the other branch.
        assert page.locator(".source pre").count() == 0

    def test_it_lands_in_the_answer_without_the_call_asking_for_that(self, page: Any) -> None:
        """The reason `diagram_create` exists rather than a fourth argument on `artifact_create`.

        The call above says nothing about placement and the picture is still in the flow of the
        answer -- a diagram explaining a paragraph is no use behind a card you open later,
        because by then the paragraph has scrolled away.

        Asserted on the shape of the card rather than on the panel being shut, which is a
        different question with a different answer: a first turn that publishes anything reopens
        the panel on it when the chat screen finishes loading (`reopenIfPublished`), inline or
        not, and that is about coming back to a conversation rather than about where this
        drawing went."""
        publish(page)

        drawn_in_the_flow = page.locator("figure.artifact.inline .drawing svg")
        drawn_in_the_flow.first.wait_for(timeout=30_000)
        assert page.locator("figure.artifact:not(.inline)").count() == 0

        # And the extension it never chose is the one the card reports.
        assert page.locator("text=MMD").count() >= 1

    def test_saving_it_gives_back_the_picture_rather_than_the_mermaid(self, page: Any) -> None:
        """What lands in a downloads folder has to be something that opens.

        Six lines of mermaid are the source of a diagram and not the diagram, and nothing on an
        ordinary machine draws a `.mmd`. So it is converted on the way out -- and it is converted
        *here*, in the browser, because mermaid lays a diagram out by measuring its own text and
        the server has no way to do that. The page carries the drawing itself rather than a
        script that would redraw it, which is what makes it still work on a machine that has
        never heard of Hera."""
        publish(page)
        page.locator("figure.artifact.inline .drawing svg").first.wait_for(timeout=30_000)

        with page.expect_download(timeout=15_000) as saving:
            page.locator("figure.artifact .save").first.click()
        saved = saving.value

        # The name she gave it, with the kind changed to the one that opens.
        assert saved.suggested_filename == "handshake.html"

        written = Path(saved.path()).read_text(encoding="utf-8")
        assert written.startswith("<!doctype html>")
        assert "<svg" in written
        # A word at a time, because that is how the markup really reads: with `htmlLabels` off
        # mermaid wraps a label by splitting it across a `<tspan>` per word, so *Client hello* is
        # one string on screen and two in the file. Asserting the sentence would be asserting
        # mermaid's line breaking.
        for word in ("Client", "hello", "Finished"):
            assert word in written
        # Not a page that fetches two megabytes of renderer to draw what is already drawn.
        # `<script` rather than `script`, because mermaid writes `aria-roledescription` into the
        # drawing and a substring search finds the word inside it.
        assert "<script" not in written
        assert "<link" not in written

    def test_the_source_is_not_what_is_on_screen(self, page: Any) -> None:
        """`flowchart TD` on screen means the renderer did not run. It was the honest fallback
        while there was nothing to run; now it would be the bug."""
        publish(page)
        page.locator(".hers .drawing svg").first.wait_for(timeout=30_000)

        assert page.locator("text=flowchart TD").count() == 0


class TestADiagramAskedForBeside:
    """`beside` is the one say the model gets, and it has to still work -- a diagram big enough
    to be the thing itself is the case ADR 13's panel was built for."""

    @pytest.fixture
    def script(self) -> list[Any]:
        return BESIDE_SCRIPT

    def test_it_is_a_card_in_the_transcript_and_the_panel_beside_it(self, page: Any) -> None:
        publish(page)

        drawing = page.locator("aside[aria-label='Artifacts'] .drawing svg")
        drawing.wait_for(timeout=30_000)
        assert "Client hello" in " ".join(drawing.locator("text").all_text_contents())

        # And what is left in the answer is the card, not the picture — the other half of the
        # same decision, and the one that says `beside` really was carried through.
        assert page.locator("figure.artifact.inline").count() == 0
        assert page.locator("figure.artifact").count() == 1


class TestWhileSheIsStillTalking:
    """A diagram that is already on screen has to survive the rest of the answer arriving.

    This is the one condition the rest of this file cannot reach. A scripted turn normally lands
    in one piece, so the transcript renders once and a view that redraws itself on every fragment
    is indistinguishable from one that does not -- which is how the bug this pins survived a
    green suite. `stream_delay` puts the fragments back on the wire one at a time.

    What went wrong is worth writing down, because it is not about diagrams. `turn.blocks` is
    rebuilt from nothing on every fragment, so the card is handed a *new* artifact object with
    the same filename in it; a prop is read through a getter, so `ArtifactView`'s effects were
    subscribed to the transcript re-rendering rather than to the file changing. Every view of an
    artifact refetched its content once per token. On an `.svg` that is invisible and merely
    wasteful; on a diagram it is a 2.7 MB renderer laying the picture out again forty times
    while she talks, which is what a person sees as the drawing above the text flickering.
    """

    @pytest.fixture
    def script(self) -> list[Any]:
        return TALKATIVE_SCRIPT

    @pytest.fixture
    def stream_delay(self) -> float:
        return 0.03

    def test_the_diagram_is_not_fetched_again_for_every_word(self, page: Any) -> None:
        """Counted as requests rather than as redraws, because the fetch is the part that is
        true of every artifact kind -- and one request per token is the shape of the bug however
        the thing is drawn afterwards.

        A small number rather than exactly one: the card and the panel are two views of the same
        file, and publishing bumps the counter that tells both to look again. What is being
        pinned is the difference between *a handful* and *one per fragment*."""
        composer = page.locator("textarea:not([disabled])").first
        composer.fill("Draw me the handshake")
        composer.press("Enter")
        page.wait_for_url("**/chat/**", timeout=15_000)

        fetched: list[str] = []
        page.on(
            "request",
            lambda request: (
                fetched.append(request.url) if "/artifacts/handshake.mmd" in request.url else None
            ),
        )

        page.locator("figure.artifact.inline .drawing svg").first.wait_for(timeout=30_000)
        page.wait_for_selector("text=THE LAST WORD", timeout=60_000)
        page.wait_for_timeout(500)

        assert len(fetched) <= 4, f"the diagram was fetched {len(fetched)} times while she talked"


class TestADiagramThatDoesNotParse:
    """The fallback has to survive the renderer landing, and this is why it is not dead code:
    the mermaid is written by a model, so *most* of the ways this feature fails are six lines
    that do not parse. Showing nothing, or showing mermaid's own error graphic, makes one bad
    line look like an artifact that came out broken -- so the source comes back, with the reason
    over it."""

    @pytest.fixture
    def script(self) -> list[Any]:
        return BROKEN_SCRIPT

    def test_it_falls_back_to_the_source_and_says_why(self, page: Any) -> None:
        publish(page)

        source = page.locator(".hers .source pre")
        source.wait_for(timeout=30_000)
        assert "steps: hello, hello back, done" in (source.inner_text() or "")

        # The caption carries mermaid's own message, which is the part naming what went wrong.
        caption = page.locator(".hers .source .caption")
        assert caption.count() == 1
        assert "did not come out" in (caption.inner_text() or "")

        # And mermaid's own error graphic is not on screen instead of it.
        assert page.locator(".drawing svg").count() == 0


class TestTheSourceCannotTurnTheLabelsOff:
    """The configuration that keeps a diagram readable has to survive the file.

    `htmlLabels: false` is what makes one sanitising path enough, and mermaid lets the *source*
    override configuration through frontmatter. The mermaid is written by a model, so this is not
    an attack to defend against -- it is a line a model will eventually write, and without
    `secure` it silently wins: every label goes back into a `<foreignObject>`, the svg-only
    profile strips it, and the diagram arrives with its boxes intact and every word gone.

    Driven in a browser for the same reason the rest of this module is, and asserted on the
    labels for the same reason too.
    """

    @pytest.fixture
    def script(self) -> list[Any]:
        return OVERRIDE_SCRIPT

    def test_frontmatter_asking_for_html_labels_does_not_get_them(self, page: Any) -> None:
        publish(page)

        drawing = page.locator("figure.artifact.inline .drawing svg").first
        drawing.wait_for(timeout=30_000)

        joined = " ".join(drawing.locator("text").all_text_contents())
        assert "Client hello" in joined
        assert "Server hello" in joined
        assert "Finished" in joined
        assert drawing.locator("foreignObject").count() == 0

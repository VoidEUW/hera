"""A mermaid artifact comes out as a picture rather than as its own source.

`.mmd` has been a real artifact kind since ADR 13 and drawn by nothing since: v0.2.0 shipped
the source view and deferred the renderer, because mermaid is two to three megabytes of browser
dependency.
[Issue #73](https://github.com/VoidEUW/hera/issues/73) is the other half of that, and the reason
it is worth having is not really the file kind -- it is that a model that can describe a flow
chart in six lines of mermaid very often cannot write the same picture as SVG path data.

Driven in a browser because nothing below one can see it: mermaid lays a diagram out by measuring
its own text, so `getBBox` has to be real.

What is pinned here is the seam that can break quietly. The drawing goes through the same
svg-only sanitiser an `.svg` artifact goes through, and mermaid's *default* label is a
`<foreignObject>` full of XHTML -- which that profile strips, correctly and catastrophically: the
boxes and the arrows arrive with no text in them at all. `$lib/mermaid` turns `htmlLabels` off so
a label is a real `<text>` element instead, and the assertion below is on the labels, because a
diagram whose words are gone still looks like a diagram from any distance.
"""

from __future__ import annotations

from typing import Any

import pytest

from hera_providers import TextDelta, TurnEnd, text_turn, tool_call

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

HANDSHAKE = "flowchart TD\n  A[Client hello] --> B[Server hello]\n  B --> C[Finished]\n"

DIAGRAM_SCRIPT: list[Any] = [
    [
        TextDelta(text="Here is the handshake.\n\n"),
        tool_call(
            "hera__artifact_create",
            {"name": "handshake.mmd", "content": HANDSHAKE, "inline": False},
        ),
        TurnEnd(reason="tool_calls"),
    ],
    text_turn("Three messages, and the last one is the cheap one."),
]

# Not a diagram at all, rather than a flow chart with a typo in it: mermaid decides what kind of
# diagram it is from the first word, so this is the one failure that cannot start passing because
# a later mermaid grew a tolerance for it.
BROKEN_SCRIPT: list[Any] = [
    [
        TextDelta(text="Here is the handshake.\n\n"),
        tool_call(
            "hera__artifact_create",
            {
                "name": "handshake.mmd",
                "content": "steps: hello, hello back, done\n",
                "inline": False,
            },
        ),
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

    def test_a_mermaid_artifact_is_drawn_with_its_labels_on_it(self, page: Any) -> None:
        """The whole of issue #73 in one assertion, and the labels are the half that is easy to
        lose: `htmlLabels` off is what lets a diagram and the sanitiser want the same thing.

        The renderer is fetched on demand, so this waits longer than a drawing she wrote herself
        would need -- that wait is the feature, not a slow test."""
        publish(page)

        drawing = page.locator("aside[aria-label='Artifacts'] .drawing svg")
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
        assert page.locator("aside[aria-label='Artifacts'] .source pre").count() == 0

    def test_the_source_is_not_what_is_on_screen(self, page: Any) -> None:
        """`flowchart TD` on screen means the renderer did not run. It was the honest fallback
        while there was nothing to run; now it would be the bug."""
        publish(page)
        page.locator("aside[aria-label='Artifacts'] .drawing svg").wait_for(timeout=30_000)

        assert page.locator("text=flowchart TD").count() == 0


class TestADiagramThatDoesNotParse:
    """The fallback has to survive the renderer landing, and this is why it is not dead code:
    the source of a `.mmd` is written by a model, so *most* of the ways this feature fails are
    six lines that do not parse. Showing nothing, or showing mermaid's own error graphic, makes
    one bad line look like an artifact that came out broken -- so the source comes back, with
    the reason over it."""

    @pytest.fixture
    def script(self) -> list[Any]:
        return BROKEN_SCRIPT

    def test_it_falls_back_to_the_source_and_says_why(self, page: Any) -> None:
        publish(page)

        source = page.locator("aside[aria-label='Artifacts'] .source pre")
        source.wait_for(timeout=30_000)
        assert "steps: hello, hello back, done" in (source.inner_text() or "")

        # The caption carries mermaid's own message, which is the part naming what went wrong.
        caption = page.locator("aside[aria-label='Artifacts'] .source .caption")
        assert caption.count() == 1
        assert "did not come out" in (caption.inner_text() or "")

        # And mermaid's own error graphic is not on screen instead of it.
        assert page.locator("aside[aria-label='Artifacts'] .drawing svg").count() == 0

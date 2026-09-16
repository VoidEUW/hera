"""A conversation holds its shape while it loads, and the drawer opens after it, not with it.

The second half of the loading pattern (#72, #115). The transcript used to be blank until the
message list landed and then appear all at once; the artifact drawer used to mount in the same
frame and take half the width, so a conversation with something published rearranged itself
twice before anybody had read a word of it.

Ordering is what these assert. That the drawer takes its width *over a beat* rather than all at
once is `ArtifactDrawer`'s `reveal` transition, and measuring an animation mid-flight from here
would be a flaky test of a thing a person is better placed to look at.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

TRANSCRIPT = "[role='status'][aria-label='Loading the conversation…']"


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


@pytest.fixture
def home(server: str) -> Path:
    """The data directory the `server` fixture made for this test, so a file can be put in it."""
    return Path(os.environ["HERA_HOME"])


def post(base: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base}/api/v1{path}",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as answer:
        return dict(json.load(answer))


def test_a_conversation_draws_its_shape_before_it_arrives(server: str, page: Any) -> None:
    chat = post(server, "/chats", {"title": "Kerberos"})

    page.goto(f"{server}/chat/{chat['id']}")

    page.wait_for_selector(TRANSCRIPT, timeout=10_000)
    # And not the invitation, which is the transcript's own empty state and the same mistake
    # the rail was making one screen over.
    assert page.get_by_text("Say something to start.").count() == 0

    page.wait_for_selector("text=Say something to start.", timeout=15_000)


#: Watches the whole load rather than sampling it once. The drawer opens off the back of its own
#: request, so *when* it would have mounted without the guard is a race -- a single `count() == 0`
#: taken after the placeholder appears passes either way, which is how this was written first and
#: why it caught nothing.
#:
#: A poll rather than a `MutationObserver`, for a duller reason: an init script runs at
#: document-start, where `document.documentElement` is still null, so `observe()` threw and the
#: flag it never got to set read back false -- a test that asserted nothing and said it passed.
WATCH = """
    window.__together = false;
    setInterval(() => {
        const placeholder = document.querySelector('[aria-label="Loading the conversation…"]');
        if (placeholder && document.querySelector('aside')) window.__together = true;
    }, 8);
"""


def test_the_drawer_waits_for_the_conversation(server: str, home: Path, page: Any) -> None:
    chat = post(server, "/chats", {"title": "Kerberos"})
    published = home / "chats" / chat["id"] / "artifacts"
    published.mkdir(parents=True)
    (published / "kerberos.md").write_text("# Kerberos\n", encoding="utf-8")

    page.add_init_script(WATCH)
    page.goto(f"{server}/chat/{chat['id']}")

    page.wait_for_selector(TRANSCRIPT, timeout=10_000)
    drawer = page.wait_for_selector("aside", timeout=15_000)
    page.wait_for_function(
        "() => { const d = document.querySelector('aside');"
        "        return d && d.getBoundingClientRect().width > 400; }",
        timeout=10_000,
    )
    assert drawer.is_visible()

    # Half the width taken away from a transcript that is still a placeholder is the screen
    # rearranging itself twice, which is what the guard is there to stop.
    assert not page.evaluate("window.__together"), "the drawer opened over the placeholder"


def test_the_drawer_opens_the_one_she_made_last(server: str, home: Path, page: Any) -> None:
    """A panel that opens onto *Nothing chosen yet* is a door that led nowhere.

    The listing arrives in name order -- `list_artifacts` walks the directory in `sorted()`
    order -- so neither end of it is *the recent one*. These three are laid out so that the file
    she wrote last is in the middle: picking the first or the last entry gets `alpha` or `gamma`,
    and only reading `modified_at` gets `beta`.
    """
    chat = post(server, "/chats", {"title": "Kerberos"})
    published = home / "chats" / chat["id"] / "artifacts"
    published.mkdir(parents=True)

    now = time.time()
    for name, ago in (("alpha.md", 300.0), ("gamma.md", 200.0), ("beta.md", 10.0)):
        written = published / name
        written.write_text(f"# {name}\n", encoding="utf-8")
        os.utime(written, (now - ago, now - ago))

    page.goto(f"{server}/chat/{chat['id']}")

    drawer = page.wait_for_selector("aside", timeout=15_000)
    assert drawer.wait_for_selector("h2", timeout=5_000).inner_text() == "Beta"
    assert page.get_by_text("Nothing chosen yet.").count() == 0

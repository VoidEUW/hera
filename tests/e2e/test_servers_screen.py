"""Settings → Servers: boxes, a tool's checkbox, and adding a server (#108).

What is asserted is what a person would check by hand — her own server is the first box, opening
a box lists its tools, unchecking one is a rule on disk that survives a reload, and a server added
on the form is connected, in the file, and removed again after asking.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest

playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed; run `uv run playwright install`"
)

pytestmark = pytest.mark.e2e

SPIKE = """
from mcp.server.mcpserver import MCPServer

server = MCPServer("spike", version="0.1.0")


@server.tool(description="Repeat the text back.")
def echo(text: str) -> str:
    return "echo:" + text


server.run(transport="stdio")
"""


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


def home() -> Path:
    return Path(os.environ["HERA_HOME"])


def open_servers(page: Any, server: str) -> None:
    page.goto(server, wait_until="networkidle")
    page.get_by_role("button", name="Settings").first.click(timeout=10_000)
    page.get_by_role("navigation", name="Settings").get_by_role("button", name="Servers").click()
    page.get_by_role("button", name="New server").wait_for(timeout=10_000)


def box(page: Any, name: str) -> Any:
    """The box named so. Its title can start with a letter in a disc, so this matches the end."""
    return page.locator("section.box").filter(
        has=page.locator("b", has_text=re.compile(rf"{re.escape(name)}\s*$"))
    )


def test_her_own_server_is_a_box_and_a_tool_can_be_switched_off(server: str, page: Any) -> None:
    open_servers(page, server)

    hers = box(page, "hera")
    hers.wait_for(timeout=5_000)
    assert page.locator("section.box").first.inner_text().startswith("hera")
    assert hers.get_by_role("button", name="Edit this server").count() == 0
    assert hers.get_by_role("button", name="Remove this server").count() == 0

    hers.locator("button.toggle").click()
    checkboxes = hers.get_by_role("checkbox")
    checkboxes.first.wait_for(timeout=10_000)
    name = checkboxes.first.get_attribute("aria-label")
    assert name
    assert checkboxes.first.is_checked()

    checkboxes.first.uncheck()
    page.wait_for_function(
        "(n) => !document.querySelector(`[aria-label='${n}']`).checked", arg=name, timeout=5_000
    )

    rules = json.loads((home() / "permissions.json").read_text(encoding="utf-8"))["rules"]
    off = next(rule for rule in rules if rule["pattern"] == f"hera__{name}")
    assert (off["decision"], off["name"]) == ("deny", "Off on the Servers screen")

    # It is what the server holds: a reload shows it still off, and the rule is on the
    # Permissions screen too.
    page.reload(wait_until="networkidle")
    open_servers(page, server)
    box(page, "hera").locator("button.toggle").click()
    page.get_by_role("checkbox", name=name).wait_for(timeout=10_000)
    assert not page.get_by_role("checkbox", name=name).is_checked()

    page.get_by_role("navigation", name="Settings").get_by_role(
        "button", name="Permissions"
    ).click()
    page.get_by_text(f"hera__{name}", exact=True).first.wait_for(timeout=5_000)


def test_a_server_added_here_connects_is_kept_and_is_removed_after_asking(
    server: str, page: Any, tmp_path: Path
) -> None:
    script = tmp_path / "spike.py"
    script.write_text(SPIKE, encoding="utf-8")
    open_servers(page, server)

    page.get_by_role("button", name="New server").click()
    dialog = page.get_by_role("dialog", name="New server")
    dialog.get_by_label("Name", exact=True).fill("spike")
    dialog.get_by_label("Command", exact=True).fill(sys.executable)
    dialog.get_by_label("Arguments").fill(str(script))
    dialog.get_by_role("button", name="Add", exact=True).first.click()
    dialog.get_by_label("Environment: Name").fill("LEVEL")
    dialog.get_by_label("Environment: Value").fill("debug")
    dialog.get_by_role("button", name="Add server").click()

    added = box(page, "spike")
    added.wait_for(timeout=10_000)
    added.get_by_text("Connected").wait_for(timeout=20_000)

    written = json.loads((home() / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["spike"]
    assert written["command"] == sys.executable
    assert written["args"] == [str(script)]
    assert written["env"] == {"LEVEL": "debug"}

    added.locator("button.toggle").click()
    added.get_by_role("checkbox", name="echo").wait_for(timeout=10_000)
    assert added.get_by_text("Repeat the text back.").count() == 1

    # Editing shows a saved secret as saved, never as its value.
    added.get_by_role("button", name="Edit this server").click()
    editor = page.get_by_role("dialog", name="Edit server")
    editor.get_by_label("Environment: Value").wait_for(timeout=5_000)
    assert editor.get_by_label("Environment: Value").input_value() == ""
    assert editor.get_by_label("Environment: Value").get_attribute("placeholder") == (
        "Saved — type to replace"
    )
    assert "debug" not in editor.inner_text()
    editor.get_by_role("button", name="Save server").click()
    editor.wait_for(state="detached", timeout=10_000)
    saved = json.loads((home() / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["spike"]
    assert saved["env"] == {"LEVEL": "debug"}

    box(page, "spike").get_by_role("button", name="Remove this server").click()
    asked = page.get_by_role("dialog", name="Remove this server?")
    asked.get_by_role("button", name="Keep it").click()
    assert box(page, "spike").count() == 1

    box(page, "spike").get_by_role("button", name="Remove this server").click()
    page.get_by_role("dialog", name="Remove this server?").get_by_role(
        "button", name="Remove"
    ).click()
    box(page, "spike").wait_for(state="detached", timeout=10_000)
    assert json.loads((home() / "mcp.json").read_text(encoding="utf-8"))["mcpServers"] == {}


def test_the_composer_counts_only_the_servers_a_person_added(server: str, page: Any) -> None:
    page.goto(server, wait_until="networkidle")
    page.get_by_role("button", name="0 servers").wait_for(timeout=10_000)

"""The letters Hera writes, and that they stay in the heaven theme (hera_core.letters)."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from hera_core import letters
from hera_core.letters import DARK, LIGHT, Palette

HEAVEN = Path(__file__).parents[1] / "web" / "src" / "lib" / "themes" / "heaven.css"


def block(css: str, selector: str) -> dict[str, str]:
    """The custom properties of the rule that starts with ``selector``."""
    start = css.index(selector)
    body = css[css.index("{", start) + 1 : css.index("}", start)]
    return dict(re.findall(r"--([a-z-]+):\s*([^;]+);", body))


@pytest.mark.parametrize(
    ("palette", "selector"), [(LIGHT, "[data-theme='light']"), (DARK, "[data-theme='dark']")]
)
def test_the_palette_is_heavens(palette: Palette, selector: str) -> None:
    """Copied, because mail cannot read the interface's CSS — and so checked against it."""
    theme = block(HEAVEN.read_text(encoding="utf-8"), selector)
    for field in fields(Palette):
        token = field.name.replace("_", "-")
        assert getattr(palette, field.name) == theme[token].strip(), token


def test_an_invitation_says_who_where_and_for_how_long() -> None:
    letter = letters.invitation(
        to="ben@hera.test", instance="Home", inviter="Ada", url="https://h.test/password#t0k"
    )
    assert letter.subject == "You are invited to Home"
    for part in (letter.text, letter.html):
        assert "https://h.test/password#t0k" in part
        assert "seven days" in part
        assert "ben@hera.test" in part
    assert 'href="https://h.test/password#t0k"' in letter.html
    assert "Choose a password" in letter.html


def test_a_reset_and_a_test_have_both_parts() -> None:
    reset = letters.reset(to="ben@hera.test", instance="Home", url="https://h.test/password#r")
    assert "an hour" in reset.text and "an hour" in reset.html
    trial = letters.trial(to="ben@hera.test", instance="Home")
    assert "mail works" in trial.text
    assert "<a " not in trial.html, "nothing to click in a test"


def test_whatever_a_person_typed_is_escaped() -> None:
    letter = letters.invitation(
        to="ben@hera.test",
        instance="<b>Home</b>",
        inviter='Ada"><script>alert(1)</script>',
        url='https://h.test/password#"onmouseover=x',
    )
    assert "<script>" not in letter.html
    assert "<b>Home</b>" not in letter.html
    assert '"onmouseover' not in letter.html
    assert "&lt;script&gt;" in letter.html


def test_dark_mode_is_offered_to_the_programs_that_follow_it() -> None:
    html = letters.reset(to="a@h.test", instance="Home", url="https://h.test/password#r").html
    assert "prefers-color-scheme: dark" in html
    assert DARK.ground in html and LIGHT.ground in html


def test_an_instance_called_hera_is_not_a_hera_called_hera() -> None:
    plain = letters.invitation(to="b@h.test", instance="Hera", inviter="Ada", url="https://h/p#t")
    named = letters.invitation(to="b@h.test", instance="Home", inviter="Ada", url="https://h/p#t")
    assert "Hera, a Hera" not in plain.text + plain.html
    assert "Home, a Hera" in named.text
    assert "Sent by Home, a Hera." in named.html

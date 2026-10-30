"""What Hera writes to people: an invitation, a password reset, the admin's test.

Each is a plain-text letter and the same letter as HTML, in the heaven theme's colours, so it
reads like the sign-in card it leads to: the ocellus, a serif heading on a pale sky, one gold
button. Mail cannot read the interface's CSS custom properties, so the palette is copied here
from ``apps/core/web/src/lib/themes/heaven.css`` — and ``test_letters.py`` reads that file and
fails when the two drift, which is the same promise ADR 21 makes for components.

The HTML is what mail programs actually render: tables for layout, every style inline, nothing
fetched — no web font, no image, no tracking pixel. A ``prefers-color-scheme`` block carries the
dark palette for the programs that honour it (Apple Mail, iCloud), and the rest show the light
one, which is the theme's own default. Every value that came from a person — a name, an
instance's name, an address — is escaped before it is placed.

English like every other string the server writes (CLAUDE.md). A link that works once, and only
for a while, says so, so whoever opens it late is not puzzled.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from hera_core.mail import Letter


@dataclass(frozen=True)
class Palette:
    ground: str
    surface: str
    surface_raised: str
    line: str
    text: str
    text_muted: str
    text_faint: str
    brass: str
    on_brass: str
    laurel: str


LIGHT = Palette(
    ground="#e5edf6",
    surface="#d7e6f4",
    surface_raised="#dde9f5",
    line="#cbdbea",
    text="#0f2338",
    text_muted="#475e77",
    text_faint="#7a8fa5",
    brass="#a87400",
    on_brass="#0f2338",
    laurel="#2574c4",
)
"""heaven.css, ``[data-theme='light']``."""

DARK = Palette(
    ground="#0f1824",
    surface="#152132",
    surface_raised="#1d2c41",
    line="#2a3d56",
    text="#eaf2fb",
    text_muted="#a3b6cb",
    text_faint="#71859b",
    brass="#f2c64e",
    on_brass="#0f1824",
    laurel="#6fb3f2",
)
"""heaven.css, ``[data-theme='dark']``."""

DISPLAY = "'Cormorant Garamond', Georgia, 'Times New Roman', serif"
UI = "'Albert Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'Fira Code', ui-monospace, Menlo, Consolas, monospace"
"""The theme's faces first, for the reader who has them, then what every system has."""


def invitation(*, to: str, instance: str, inviter: str, url: str) -> Letter:
    who = inviter or "Somebody"
    return Letter(
        to=to,
        subject=f"You are invited to {instance}",
        text=(
            f"{who} has made you an account on {_called(instance)}.\n\n"
            f"Choose a password here to sign in as {to}:\n\n{url}\n\n"
            "The link works once, for seven days. If you were not expecting this, you can "
            "ignore it.\n"
        ),
        html=_page(
            instance=instance,
            preheader=f"{who} has made you an account on {instance}.",
            heading=f"You are invited to {instance}",
            paragraphs=[
                f"{escape(who)} has made you an account on <strong>{escape(instance)}</strong>"
                f"{escape(_called(instance)[len(instance) :])} — your own chats, memories and mind.",
                f"Choose a password to sign in as <strong>{escape(to)}</strong>.",
            ],
            button=("Choose a password", url),
            note="The link works once, for seven days. If you were not expecting this, you can "
            "ignore this mail.",
        ),
    )


def reset(*, to: str, instance: str, url: str) -> Letter:
    return Letter(
        to=to,
        subject=f"Reset your password on {instance}",
        text=(
            f"Somebody asked to reset the password of {to} on {instance}.\n\n"
            f"Choose a new password here:\n\n{url}\n\n"
            "The link works once, for an hour, and choosing a password signs you out everywhere "
            "else. If it was not you, ignore this mail — your password stays as it is.\n"
        ),
        html=_page(
            instance=instance,
            preheader=f"A link to choose a new password on {instance}.",
            heading="Reset your password",
            paragraphs=[
                f"Somebody asked to reset the password of <strong>{escape(to)}</strong> on "
                f"{escape(instance)}.",
                "Choose a new one, and you are signed in.",
            ],
            button=("Choose a new password", url),
            note="The link works once, for an hour, and choosing a password signs you out "
            "everywhere else. If it was not you, ignore this mail — your password stays as it is.",
        ),
    )


def trial(*, to: str, instance: str) -> Letter:
    return Letter(
        to=to,
        subject=f"A test from {instance}",
        text=f"This is {instance}. If you are reading this, mail works.\n",
        html=_page(
            instance=instance,
            preheader="If you are reading this, mail works.",
            heading="Mail works",
            paragraphs=[
                f"This is {escape(instance)}. If you are reading this, invitations and password "
                "resets will reach people too."
            ],
            button=None,
            note="Sent because an admin pressed “Send a test mail” on Settings → Admin → Mail.",
        ),
    )


def _called(instance: str) -> str:
    """``Home, a Hera`` — or just ``Hera``, for the instance nobody renamed."""
    return instance if instance.strip().lower() == "hera" else f"{instance}, a Hera"


# -- the page --------------------------------------------------------------------------------------


def _page(
    *,
    instance: str,
    preheader: str,
    heading: str,
    paragraphs: list[str],
    button: tuple[str, str] | None,
    note: str,
) -> str:
    """One card on the ground, under the mark. ``paragraphs`` are already HTML; everything else
    is text and is escaped here."""
    c = LIGHT
    body = "".join(
        f'<p class="hm-text" style="margin:0 0 14px;color:{c.text};">{paragraph}</p>'
        for paragraph in paragraphs
    )
    action = _button(*button) if button else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{escape(heading)}</title>
<style>{_dark()}</style>
</head>
<body class="hm-body" style="margin:0;padding:0;background:{c.ground};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
 class="hm-body" style="background:{c.ground};">
<tr><td align="center" style="padding:40px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
 style="max-width:520px;">
<tr><td align="center" style="padding:0 0 18px;">
{_mark()}
<div class="hm-muted" style="margin-top:10px;font-family:{DISPLAY};font-size:20px;color:{c.text_muted};">{escape(instance)}</div>
</td></tr>
<tr><td class="hm-card" style="background:{c.surface};border:1px solid {c.line};border-radius:16px;padding:32px 30px;font-family:{UI};font-size:15px;line-height:1.55;color:{c.text};">
<h1 class="hm-text" style="margin:0 0 16px;font-family:{DISPLAY};font-size:30px;line-height:1.15;font-weight:500;color:{c.text};">{escape(heading)}</h1>
{body}
{action}
<p class="hm-faint" style="margin:22px 0 0;padding-top:16px;border-top:1px solid {c.line};font-size:13px;color:{c.text_faint};">{escape(note)}</p>
</td></tr>
<tr><td align="center" class="hm-faint" style="padding:18px 8px 0;font-family:{UI};font-size:12px;color:{c.text_faint};">
Sent by {escape(_called(instance))}.
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""


def _button(label: str, url: str) -> str:
    """The theme's highlighted button, built the way mail programs keep it: a coloured cell
    around a link, so it is a button even where padding on an ``<a>`` is ignored. The link is
    also written out beneath it, for the program that strips buttons and the reader who would
    rather paste it."""
    c = LIGHT
    href = escape(url, quote=True)
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 18px;">
<tr><td class="hm-button" bgcolor="{c.brass}" style="background:{c.brass};border-radius:8px;">
<a class="hm-button" href="{href}" style="display:inline-block;padding:12px 24px;font-family:{UI};font-size:15px;font-weight:600;color:{c.on_brass};text-decoration:none;border-radius:8px;">{escape(label)}</a>
</td></tr>
</table>
<p class="hm-muted" style="margin:0 0 6px;font-size:13px;color:{c.text_muted};">Or open this link:</p>
<p style="margin:0;font-family:{MONO};font-size:12px;word-break:break-all;"><a class="hm-link" href="{href}" style="color:{c.laurel};text-decoration:none;">{escape(url)}</a></p>"""


def _mark() -> str:
    """The ocellus — a gold ring, a blue iris, a dark pupil — in nested cells and rounded
    blocks, because an SVG is something most mail programs will not draw."""
    c = LIGHT
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center">
<tr><td class="hm-ring" align="center" valign="middle" width="22" height="22" style="width:22px;height:22px;border:3px solid {c.brass};border-radius:50%;">
<div class="hm-iris" style="width:12px;height:12px;margin:0 auto;padding-top:4px;box-sizing:border-box;border-radius:50%;background:{c.laurel};">
<div class="hm-pupil" style="width:4px;height:4px;margin:0 auto;border-radius:50%;background:{c.ground};"></div>
</div>
</td></tr>
</table>"""


def _dark() -> str:
    """The dark palette, for a reader whose mail program follows the system's appearance."""
    d = DARK
    rules = {
        ".hm-body": f"background:{d.ground}",
        ".hm-card": f"background:{d.surface};border-color:{d.line}",
        ".hm-text": f"color:{d.text}",
        ".hm-muted": f"color:{d.text_muted}",
        ".hm-faint": f"color:{d.text_faint};border-color:{d.line}",
        "td.hm-button": f"background:{d.brass}",
        "a.hm-button": f"color:{d.on_brass}",
        ".hm-link": f"color:{d.laurel}",
        ".hm-ring": f"border-color:{d.brass}",
        ".hm-iris": f"background:{d.laurel}",
        ".hm-pupil": f"background:{d.ground}",
    }
    body = "".join(
        f"{selector}{{{';'.join(f'{rule} !important' for rule in declarations.split(';'))}}}"
        for selector, declarations in rules.items()
    )
    return f"@media (prefers-color-scheme: dark){{{body}}}"

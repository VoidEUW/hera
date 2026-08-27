"""The stances she can show, as data.

``hera__emotion(kind, text)`` takes free text for ``kind`` — ADR 3 is explicit that the model
may invent one and that an unknown kind renders generically. What this module holds is the
*starting vocabulary*: a word, a sentence saying when it is honest to use it, and the tone the
interface draws it in.

**Why data rather than prose.** The vocabulary used to be a paragraph inside a mind region,
which meant the interface could not know that ``doubt`` is cool and ``warn`` is careful without
a second copy of the list in the browser. As data it renders into the prompt *and* colours the
card from one place, and a person can add a stance of their own without either half going
stale.

**Why not in the tool description.** The description is fixed when the MCP server is built, and
a vocabulary you can edit on screen has to apply on the next turn rather than the next restart.
So the tool says only that ``kind`` is a short word it may invent, and the list travels in the
prompt, which is assembled per turn.

Nothing here reads a file. Where the person's own list is kept is `hera_core.emotions`; this
package imports nothing and does no I/O.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Tone = Literal["warm", "cool", "sharp", "soft"]
"""How the card is drawn. Four, not fourteen: a colour per kind would be a palette nobody can
read, and an invented kind has to land somewhere sensible."""


class Emotion(BaseModel):
    """One stance in the vocabulary."""

    model_config = ConfigDict(frozen=True)

    kind: str = Field(min_length=1, max_length=32)
    """The word the model passes as ``kind``. Lowercase, one word — it is a label on a card."""

    description: str = Field(default="", max_length=200)
    """When it is honest to use this one, written for the model to read."""

    tone: Tone = "soft"


DEFAULT_EMOTIONS: tuple[Emotion, ...] = (
    Emotion(kind="agree", description="You are with them, and it is worth saying so.", tone="warm"),
    Emotion(kind="disagree", description="You think they are wrong about this.", tone="sharp"),
    Emotion(kind="doubt", description="Something in the premise does not hold up.", tone="cool"),
    Emotion(kind="surprised", description="This is not what you expected.", tone="cool"),
    Emotion(kind="funny", description="Something here is genuinely funny.", tone="warm"),
    Emotion(kind="joke", description="You are being playful on purpose.", tone="warm"),
    Emotion(
        kind="warn", description="There is a risk they should see before going on.", tone="sharp"
    ),
    Emotion(kind="ask", description="You need something from them to go further.", tone="cool"),
    Emotion(kind="curious", description="You want to know more about this.", tone="cool"),
    Emotion(kind="hope", description="You want this to work out for them.", tone="warm"),
    Emotion(kind="excited", description="This is genuinely interesting to you.", tone="warm"),
    Emotion(kind="sorry", description="Something went wrong and it was yours.", tone="soft"),
    Emotion(
        kind="annoyed", description="Something is repeatedly getting in the way.", tone="sharp"
    ),
    Emotion(kind="judge", description="You have a verdict and you are giving it.", tone="sharp"),
)
"""The set she starts with, documented in the ``emotions`` section of the prompt.

Fourteen words. A person can change any of them, add their own, or put the whole list back —
which is the point of it being a list rather than a constant in a prompt.
"""


def render_emotions(emotions: tuple[Emotion, ...] | list[Emotion]) -> str:
    """The vocabulary as the model reads it, one line per stance.

    Ends by granting the freedom ADR 3 requires: a model that hard-obeys its inputs will never
    invent a kind unless the list says it may, and the whole point of the open vocabulary is
    that she can be something none of these words covers.
    """
    lines = [
        f"- {emotion.kind}: {emotion.description}" if emotion.description else f"- {emotion.kind}"
        for emotion in emotions
    ]
    if not lines:
        return ""
    return "\n".join(
        [
            "Stances you can show with hera__emotion:",
            *lines,
            "",
            "This is a starting vocabulary and not a closed list. Invent a kind when none of "
            "these is honest.",
        ]
    )

"""What the browser could not draw, remembered until somebody changes it.

The server cannot tell whether a diagram parses or an SVG is well-formed: mermaid lays a diagram
out by measuring its own text, and only a browser can. So the browser says so — one report per
artifact, from the component that tried to draw it — and the next turn tells her, in the same
place it tells her the date. Without this a bad diagram was visible to everyone except the one
who wrote it, and a model that is never told a syntax does not work writes the same one again.

**A report is about one version of a file.** It records the size and modification time it was
made against, and is dropped when either has moved: an edit is exactly the thing that answers
it, and a stale complaint about a diagram she already fixed would send her to fix it twice.

In memory and not on disk, on purpose. It is feedback for the next turn or two rather than a
record, and a restart forgetting one costs a redraw the next time the person opens the file —
which reports it again.
"""

from __future__ import annotations

from dataclasses import dataclass

from hera_core.chat_files import ChatFileRefused, _resolve
from hera_home import artifacts_dir

__all__ = ["MAX_MESSAGE", "ArtifactProblems", "problems"]

MAX_MESSAGE = 400
"""Characters of a report that reach the prompt.

A parse error names the line and quotes a little of it, which is the useful part; anything longer
is the source over again, and the model wrote that.
"""


@dataclass(frozen=True)
class _Report:
    message: str
    size: int
    modified: float


class ArtifactProblems:
    """The current complaint about each artifact, per conversation."""

    def __init__(self) -> None:
        self._reports: dict[tuple[str, str], _Report] = {}

    def report(self, chat_id: str, name: str, message: str) -> bool:
        """Note that this file did not draw. ``False`` if there is no such file to note it on."""
        try:
            target = _resolve(artifacts_dir(chat_id), name)
        except ChatFileRefused:
            return False
        if not target.is_file():
            return False
        seen = target.stat()
        text = " ".join(message.split())[:MAX_MESSAGE]
        self._reports[(chat_id, target.name)] = _Report(text, seen.st_size, seen.st_mtime)
        return True

    def recall(self, chat_id: str) -> str:
        """What to tell her, rendered for the ``problems`` slot; ``""`` when there is nothing."""
        lines: list[str] = []
        for (chat, name), found in sorted(self._reports.items()):
            if chat != chat_id:
                continue
            if not self._still_true(chat, name, found):
                del self._reports[(chat, name)]
                continue
            lines.append(f"- `{name}`: {found.message}")
        if not lines:
            return ""
        return (
            "These did not draw in the person's browser, so they are looking at the source "
            "rather than the picture. Say so if it comes up, and fix them with `artifact_edit` "
            "or by drawing them again:\n" + "\n".join(lines)
        )

    def _still_true(self, chat_id: str, name: str, found: _Report) -> bool:
        try:
            seen = _resolve(artifacts_dir(chat_id), name).stat()
        except (ChatFileRefused, OSError):
            return False
        return seen.st_size == found.size and seen.st_mtime == found.modified


problems = ArtifactProblems()
"""The one in use. A module attribute rather than something the container holds, because the
route that fills it and the turn that reads it are in different files and neither owns it."""

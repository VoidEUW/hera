"""Server-Sent Events: a turn on the wire.

Hand-rolled rather than pulled from a library, because the format is four lines and the two
things that usually justify a library — reconnection and keep-alive pings — are either the
browser's job or actively unwanted here. ``EventSource`` reconnects on its own; a keep-alive
would hold a turn open past the point where the person navigated away, and a disconnected
consumer is exactly the signal ``hera_chats`` uses to close a turn as `cancelled`.

Each frame carries the event's own ``type`` as the SSE event name **and** inside the JSON. The
name is what a client attaches a listener to; the field is what survives being persisted. They
are the same string, from the same place, so they cannot drift.

Two frames are the transport's own rather than a `ChatEvent`:

``done`` carries the **persisted** message and is what makes the server render authoritative.
The client throws away everything it rendered optimistically and re-renders from that payload,
so a live view and a reload cannot disagree (ADR 6).

``error`` is for a failure before the turn started — an unknown chat, a database that will not
open. Once the turn is running, failures arrive as ``turn_closed`` with a reason, because at
that point there is a half-written answer worth keeping.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from hera_chats import CHAT_EVENT_ADAPTER, ChatEvent

MEDIA_TYPE = "text/event-stream"

HEADERS: Mapping[str, str] = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    # Nginx buffers proxied responses by default, which turns a stream into one delivery at
    # the end. Self-hosting behind a reverse proxy is the normal deployment, so this is not a
    # detail somebody should have to discover.
    "X-Accel-Buffering": "no",
}


def frame(name: str, payload: Any) -> str:
    """One SSE frame.

    ``json.dumps`` without indentation on purpose: a newline inside the data of an SSE frame
    starts a new ``data:`` line, and while the spec says a client should rejoin them, a
    single-line payload removes the question.
    """
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"event: {name}\ndata: {body}\n\n"


def event_frame(event: ChatEvent) -> str:
    """One ``ChatEvent`` as a frame, named by its own ``type``."""
    return frame(event.type, CHAT_EVENT_ADAPTER.dump_python(event, mode="json"))

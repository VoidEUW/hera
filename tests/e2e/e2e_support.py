"""What the browser suite imports by name: the server it drives, signed in.

Not in `conftest.py`, which mypy skips (see the root `pyproject.toml`), and which a test module
cannot import from anyway.
"""

from __future__ import annotations

import json
import socketserver
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from email import message_from_string
from email.policy import default
from pathlib import Path
from typing import Any
from uuid import UUID

OWNER_EMAIL = "owner@hera.test"
OWNER_PASSWORD = "correct horse battery"


class Served(str):
    """The server's base URL — a ``str``, so ``f"{server}/chat"`` reads as it always did — and
    the session of the admin it was set up with (ADR 27)."""

    token: str

    def __new__(cls, url: str, token: str) -> Served:
        served = super().__new__(cls, url)
        served.token = token
        return served

    @property
    def headers(self) -> dict[str, str]:
        """For a request made outside the browser."""
        from hera_core.auth import SESSION_COOKIE

        return {"cookie": f"{SESSION_COOKIE}={self.token}"}

    def sign_in(self, context: Any) -> Any:
        """Put the admin's session cookie into a Playwright browser context."""
        from hera_core.auth import SESSION_COOKIE

        context.add_cookies([{"name": SESSION_COOKIE, "value": self.token, "url": str(self)}])
        return context


def claim(database: Any, owner_id: UUID) -> str:
    """Make the first admin the setup wizard would, and open a session for them.

    ``database`` is a ``hera_storage.Database``. Returns the session token.
    """
    from hera_accounts import Accounts, Role

    with database.session() as session:
        accounts = Accounts(session)
        accounts.create(OWNER_EMAIL, role=Role.ADMIN, password=OWNER_PASSWORD, user_id=owner_id)
        token, _ = accounts.open_session(owner_id)
    return token


def written(path: Path, until: Callable[[dict[str, Any]], bool] = lambda _: True) -> dict[str, Any]:
    """A JSON file the server writes, once it says what ``until`` expects (or after 5 s).

    Waited for rather than read once: a screen shows a change as soon as it has asked for it,
    and the file is written when the server has answered — the two are a request apart, and a
    test that reads in between is testing the scheduler.
    """
    deadline = time.monotonic() + 5
    while True:
        try:
            found = dict(json.loads(path.read_text(encoding="utf-8")))
            if until(found) or time.monotonic() > deadline:
                return found
        except (FileNotFoundError, json.JSONDecodeError):
            if time.monotonic() > deadline:
                raise
        time.sleep(0.05)


class _Conversation(socketserver.StreamRequestHandler):
    """Just enough SMTP to take a message: what ``smtplib`` says, answered in order."""

    server: MailSink

    def handle(self) -> None:
        self.wfile.write(b"220 sink\r\n")
        body: list[str] | None = None
        while line := self.rfile.readline():
            text = line.decode(errors="replace").rstrip("\r\n")
            if body is not None:
                if text == ".":
                    self.server.received(message_from_string("\n".join(body), policy=default))
                    body = None
                    self.wfile.write(b"250 queued\r\n")
                else:
                    body.append(text[1:] if text.startswith("..") else text)
            elif text.upper().startswith("DATA"):
                body = []
                self.wfile.write(b"354 go on\r\n")
            elif text.upper().startswith("QUIT"):
                self.wfile.write(b"221 bye\r\n")
                return
            else:
                self.wfile.write(b"250 ok\r\n")


class MailSink(socketserver.ThreadingTCPServer):
    """A mail server on a free local port that keeps the text of every message it is sent."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Conversation)
        self.texts: list[str] = []
        self._arrived = threading.Condition()

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    def received(self, message: Any) -> None:
        with self._arrived:
            # The plain part: what a link is read out of, whatever HTML rides beside it.
            self.texts.append(str(message.get_body(preferencelist=("plain",)).get_content()))
            self._arrived.notify_all()

    def next_text(self, timeout: float = 10.0) -> str:
        """The oldest message not yet read, waiting for it to arrive."""
        with self._arrived:
            if not self._arrived.wait_for(lambda: bool(self.texts), timeout=timeout):
                raise TimeoutError("no mail arrived")
            return self.texts.pop(0)


@contextmanager
def mail_sink() -> Iterator[MailSink]:
    sink = MailSink()
    thread = threading.Thread(target=sink.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    try:
        yield sink
    finally:
        sink.shutdown()
        sink.server_close()

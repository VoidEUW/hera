"""The SMTP adapter, against a mail server small enough to read: a socket that speaks just
enough SMTP to take a message, refuse a recipient, and turn down a password or STARTTLS."""

from __future__ import annotations

import base64
import contextlib
import socket
import socketserver
import threading
from collections.abc import Iterator
from email import message_from_string
from email.policy import default
from email.utils import parsedate_to_datetime
from typing import Any

import pytest

from hera_core import mail
from hera_core.config import MailConfig
from hera_core.mail import Letter, MailError, Postbox, SmtpMailer


class Sink(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), Conversation)
        self.messages: list[str] = []
        self.logins: list[tuple[str, str]] = []

    @property
    def port(self) -> int:
        return int(self.server_address[1])


class Conversation(socketserver.StreamRequestHandler):
    server: Sink

    def say(self, *lines: str) -> None:
        for index, line in enumerate(lines):
            joiner = "-" if index < len(lines) - 1 else " "
            code, _, text = line.partition(" ")
            self.wfile.write(f"{code}{joiner}{text}\r\n".encode())

    def handle(self) -> None:
        # The client may hang up mid-sentence — a TLS hello that got no answer it understood.
        with contextlib.suppress(OSError):
            self.converse()

    def converse(self) -> None:
        self.say("220 sink ready")
        body: list[str] | None = None
        busy = False
        while line := self.rfile.readline():
            text = line.decode(errors="replace").rstrip("\r\n")
            if body is not None:
                if text == ".":
                    self.server.messages.append("\n".join(body))
                    body = None
                    self.say("250 queued")
                else:
                    body.append(text[1:] if text.startswith("..") else text)
                continue
            verb = text.split(" ", 1)[0].upper()
            if verb == "EHLO":
                self.say("250 sink", "250 AUTH PLAIN", "250 OK")
            elif verb == "AUTH":
                _, user, password = base64.b64decode(text.split()[-1]).decode().split("\0")
                self.server.logins.append((user, password))
                self.say("235 ok" if password == "right" else "535 no")
            elif verb == "MAIL":
                busy = "busy" in text
                self.say("553 sender not yours" if "stranger" in text else "250 ok")
            elif verb == "RCPT":
                self.say("550 no such mailbox" if "nobody" in text else "250 ok")
            elif verb == "DATA" and busy:
                self.say("451 Requested action aborted: local error in processing")
            elif verb == "DATA":
                body = []
                self.say("354 go on")
            elif verb == "QUIT":
                self.say("221 bye")
                return
            else:
                self.say("250 ok")


@pytest.fixture
def sink() -> Iterator[Sink]:
    server = Sink()
    thread = threading.Thread(target=server.serve_forever, args=(0.02,), daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def config(sink: Sink, **changes: Any) -> MailConfig:
    return MailConfig.model_validate(
        {
            "host": "127.0.0.1",
            "port": sink.port,
            "security": "none",
            "sender": "hera@hera.test",
            **changes,
        }
    )


LETTER = Letter(to="ana@hera.test", subject="Hello", text="A line.\n.\nAnother.")


def test_a_letter_arrives_with_the_instance_as_its_sender(sink: Sink) -> None:
    SmtpMailer(timeout=5).send(config(sink), LETTER, sender_name="Hera at home")

    [raw] = sink.messages
    message = message_from_string(raw, policy=default)
    assert message["From"] == "Hera at home <hera@hera.test>"
    assert message["To"] == "ana@hera.test"
    assert message["Subject"] == "Hello"
    assert message["Message-ID"].endswith("@hera.test>")
    assert parsedate_to_datetime(message["Date"]).tzinfo is not None, "RFC 5322 requires a date"
    assert message["Auto-Submitted"] == "auto-generated"
    for header in ("From", "Date", "Message-ID"):
        assert len(message.get_all(header, [])) == 1, f"exactly one {header}"
    assert str(message.get_content()).strip() == "A line.\n.\nAnother."
    assert sink.logins == [], "no user, no sign-in"


def test_a_user_signs_in_and_a_wrong_password_is_said_so(sink: Sink) -> None:
    SmtpMailer(timeout=5).send(config(sink, user="hera", password="right"), LETTER, sender_name="H")
    assert sink.logins == [("hera", "right")]

    with pytest.raises(
        MailError, match=r"did not accept the user hera and that password \(535 no\)"
    ):
        SmtpMailer(timeout=5).send(
            config(sink, user="hera", password="wrong"), LETTER, sender_name="H"
        )


def test_a_refused_recipient_is_named(sink: Sink) -> None:
    nobody = Letter(to="nobody@hera.test", subject="s", text="t")
    with pytest.raises(MailError, match=r"refused to deliver to nobody@hera\.test"):
        SmtpMailer(timeout=5).send(config(sink), nobody, sender_name="H")


def test_starttls_on_a_server_without_it_says_what_to_try(sink: Sink) -> None:
    with pytest.raises(MailError, match="does not offer STARTTLS"):
        SmtpMailer(timeout=5).send(config(sink, security="starttls"), LETTER, sender_name="H")


def test_tls_to_a_plain_server_fails_as_mail_not_as_a_crash(sink: Sink) -> None:
    with pytest.raises(MailError, match=r"could not send through 127\.0\.0\.1"):
        SmtpMailer(timeout=5).send(config(sink, security="tls"), LETTER, sender_name="H")


def test_nothing_listening_is_a_mail_error() -> None:
    closed = Sink()
    port = closed.port
    closed.server_close()
    settings = MailConfig(host="127.0.0.1", port=port, security="none", sender="h@hera.test")
    with pytest.raises(MailError, match="could not send"):
        SmtpMailer(timeout=2).send(settings, LETTER, sender_name="H")


@pytest.mark.parametrize("mailer", [SmtpMailer(), Postbox()])
def test_mail_that_is_not_set_up_is_not_sent(mailer: Any) -> None:
    with pytest.raises(MailError, match="not set up"):
        mailer.send(MailConfig(host="smtp.hera.test"), LETTER, sender_name="H")


def test_a_link_carries_its_token_after_the_hash() -> None:
    assert mail.link("https://hera.example.com/", "abc") == "https://hera.example.com/password#abc"


def test_the_password_never_leaves_in_the_redacted_form() -> None:
    shown = MailConfig(host="h", sender="s@h.test", password="secret").redacted()
    assert "password" not in shown
    assert shown["password_set"] is True
    assert shown["configured"] is True


def test_a_name_that_does_not_resolve_says_so_in_words(monkeypatch: pytest.MonkeyPatch) -> None:
    def unresolvable(*_: Any, **__: Any) -> None:
        raise socket.gaierror(8, "nodename nor servname provided, or not known")

    monkeypatch.setattr("smtplib.SMTP", unresolvable)
    settings = MailConfig(host="smtp.example.test", sender="h@hera.test")
    with pytest.raises(MailError, match=r"smtp\.example\.test could not be looked up"):
        SmtpMailer().send(settings, LETTER, sender_name="H")


def test_a_sender_the_account_may_not_use_is_named(sink: Sink) -> None:
    settings = config(sink, sender="stranger@hera.test", user="hera", password="right")
    with pytest.raises(MailError) as refused:
        SmtpMailer(timeout=5).send(settings, LETTER, sender_name="H")
    assert str(refused.value) == (
        "the mail server would not send as stranger@hera.test (553 sender not yours)"
        " — is hera allowed to send from that address?"
    )


def test_a_4xx_says_it_is_temporary_and_keeps_the_servers_words(sink: Sink) -> None:
    with pytest.raises(MailError) as busy:
        SmtpMailer(timeout=5).send(config(sink, sender="busy@hera.test"), LETTER, sender_name="H")
    assert str(busy.value) == (
        "the mail server would not take the message"
        " (451 Requested action aborted: local error in processing);"
        " that is temporary on its side, so try again in a few minutes"
    )


def test_a_letter_with_html_arrives_as_both(sink: Sink) -> None:
    letter = Letter(to="ana@hera.test", subject="Hi", text="Plain.", html="<p>Rich.</p>")
    named = config(sink, sender_name="Hera")
    SmtpMailer(timeout=5).send(named, letter, sender_name="Home")

    message = message_from_string(sink.messages[0], policy=default)
    assert message["From"] == "Hera <hera@hera.test>", "the From name wins over the instance's"
    assert message.get_content_type() == "multipart/alternative"
    plain, rich = (part.get_content_type() for part in message.iter_parts())
    assert (plain, rich) == ("text/plain", "text/html")

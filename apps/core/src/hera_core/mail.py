"""Mail: invitations, password resets and the admin's test message (ADR 27).

A port and one adapter. The port is what a route holds, so a test hands it a postbox that keeps
what was sent instead of a server that would have to exist. The adapter is the standard
library's ``smtplib``, which is blocking — every caller is a synchronous route or a background
task, and both already run in a worker thread, off the event loop.

**A link is built here, and only from somewhere trusted.** A token in a mail is as good as the
account it opens, so where the link points matters as much as the token: a link built from the
request's ``Host`` is a link a stranger can aim at their own server by asking for a reset with a
forged header. Mail an anonymous request causes is therefore built from the instance's public
URL or not sent at all; mail a signed-in person causes may use the address their own browser
used. The token goes after ``#``, so it never reaches a server's access log or a ``Referer``.
"""

from __future__ import annotations

import smtplib
import socket
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Protocol

from hera_core.config import MailConfig

TIMEOUT_S = 15.0
"""How long a mail server may take to answer. An invitation is sent while an admin waits."""

LINK_PATH = "/password"
"""The page an invitation or a reset link opens: choose a password, and be signed in."""


@dataclass(frozen=True)
class Letter:
    """One message. ``text`` is always sent; ``html`` rides beside it as the alternative a mail
    program shows when it can (``hera_core.letters`` writes both)."""

    to: str
    subject: str
    text: str
    html: str = ""


class MailError(RuntimeError):
    """The mail did not go. The message says why, in words for whoever configured the server."""


class Mailer(Protocol):
    def send(self, config: MailConfig, letter: Letter, *, sender_name: str) -> None:
        """``sender_name`` is the fallback for the ``From`` name — the instance's — when
        ``[mail]`` names none of its own."""
        ...


def from_header(config: MailConfig, fallback_name: str) -> str:
    """``Hera <hera@example.com>``: what a person sees the mail come from."""
    return formataddr((config.sender_name or fallback_name, config.sender))


class SmtpMailer:
    """Sends one letter per connection. Hera sends a handful a day; a pool would be a cache of
    connections the server has long since closed."""

    def __init__(self, *, timeout: float = TIMEOUT_S) -> None:
        self.timeout = timeout

    def send(self, config: MailConfig, letter: Letter, *, sender_name: str) -> None:
        if not config.configured:
            raise MailError("mail is not set up here")
        message = EmailMessage()
        message["From"] = from_header(config, sender_name)
        message["To"] = letter.to
        message["Subject"] = letter.subject
        # Required by RFC 5322, and added by neither `email` nor `smtplib`. Many submission
        # servers do not fill it in for an authenticated client either, and a strict receiver
        # (iCloud answers `554 5.7.1 [HM08]`) refuses the message after the server took it.
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain=config.sender.rpartition("@")[2] or None)
        # RFC 3834: sent by a program, for one person who asked. Receivers read it as
        # transactional, and an out-of-office reply knows not to answer it.
        message["Auto-Submitted"] = "auto-generated"
        message.set_content(letter.text)
        if letter.html:
            message.add_alternative(letter.html, subtype="html")
        try:
            with self._connect(config) as smtp:
                if config.security == "starttls":
                    smtp.starttls(context=ssl.create_default_context())
                if config.user:
                    smtp.login(config.user, config.password)
                smtp.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            raise MailError(
                _refusal(exc, f"did not accept the user {config.user} and that password")
                + " — some providers (iCloud, Gmail) need an app-specific password here, not "
                "the account's own"
            ) from None
        except smtplib.SMTPNotSupportedError:
            raise MailError(
                "the mail server does not offer STARTTLS; try TLS on port 465, or none"
            ) from None
        except smtplib.SMTPRecipientsRefused:
            raise MailError(f"the mail server refused to deliver to {letter.to}") from None
        except smtplib.SMTPSenderRefused as exc:
            raise MailError(
                _refusal(exc, f"would not send as {config.sender}")
                + (
                    ""
                    if _temporary(exc)
                    else f" — is {config.user or 'this account'} allowed to send from that address?"
                )
            ) from None
        except smtplib.SMTPDataError as exc:
            raise MailError(_refusal(exc, "would not take the message")) from None
        except smtplib.SMTPResponseException as exc:
            raise MailError(_refusal(exc, "answered with an error")) from None
        except socket.gaierror:
            raise MailError(
                f"{config.host} could not be looked up — check the spelling, or whether this "
                "machine's DNS can resolve it right now"
            ) from None
        except (smtplib.SMTPException, ssl.SSLError, OSError) as exc:
            raise MailError(f"could not send through {config.host}:{config.port}: {exc}") from None

    def _connect(self, config: MailConfig) -> smtplib.SMTP:
        if config.security == "tls":
            return smtplib.SMTP_SSL(
                config.host,
                config.port,
                timeout=self.timeout,
                context=ssl.create_default_context(),
            )
        return smtplib.SMTP(config.host, config.port, timeout=self.timeout)


def _temporary(exc: smtplib.SMTPResponseException) -> bool:
    """A 4xx: the server could not do it *now*, which is a different thing to fix than a 5xx."""
    return 400 <= exc.smtp_code < 500


def _refusal(exc: smtplib.SMTPResponseException, what: str) -> str:
    """The server's own code and words, which are what its operator documents and what a search
    finds — and, for a 4xx, that waiting is the remedy rather than changing a setting."""
    said = exc.smtp_error.decode(errors="replace") if isinstance(exc.smtp_error, bytes) else ""
    said = " ".join(said.split())
    sentence = f"the mail server {what} ({exc.smtp_code} {said})".replace(" )", ")")
    if _temporary(exc):
        sentence += "; that is temporary on its side, so try again in a few minutes"
    return sentence


@dataclass
class Postbox:
    """A mailer that keeps what it was given — for tests, and anything else that wants to look
    at a letter instead of sending it. ``failure`` makes every send raise it."""

    sent: list[Letter] = field(default_factory=list)
    froms: list[str] = field(default_factory=list)
    failure: str = ""

    def send(self, config: MailConfig, letter: Letter, *, sender_name: str) -> None:
        if not config.configured:
            raise MailError("mail is not set up here")
        if self.failure:
            raise MailError(self.failure)
        self.sent.append(letter)
        self.froms.append(from_header(config, sender_name))


def link(base: str, token: str) -> str:
    """Where a token is used. The token is the fragment, so no server ever logs it."""
    return f"{base.rstrip('/')}{LINK_PATH}#{token}"

"""Invitation and reset links: making one for somebody, and getting it to them (ADR 27).

Three routes hand out links — an invitation, an admin's *reset link* on Settings → Users, and
*forgot your password?* — and they differ only in who asked and what the letter says. This is the
part they share: one live link per person and purpose, mailed when mail is set up, and handed
back when it is not or the mail server said no.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Request

from hera_accounts import INVITE_LIFETIME, RESET_LIFETIME, Accounts, Purpose, User
from hera_core import letters, mail
from hera_core.addresses import reachable_base
from hera_core.config import HeraConfig
from hera_core.mail import Letter, Mailer, MailError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Sent:
    link: str
    mailed: bool
    mail_error: str = ""


def base_for(request: Request, config: HeraConfig, *, bind_host: str) -> str:
    """Where a link a *signed-in* person asked for points: the public URL, or else the address
    their own browser reached this server at — either way never ``0.0.0.0`` or ``localhost``,
    which would send the person it is for to their own machine (:mod:`hera_core.addresses`).
    Never for an anonymous request — see :mod:`hera_core.mail`."""
    base = config.instance.public_url or str(request.base_url)
    return reachable_base(base, bind_host=bind_host)


def purpose_for(accounts: Accounts, user: User) -> Purpose:
    """An account with no password yet is still an invitation; one with a password is reset."""
    return Purpose.RESET if accounts.has_password(user.id) else Purpose.INVITE


def issue(accounts: Accounts, user: User, purpose: Purpose) -> str:
    """A new token for this person, and every earlier unspent one of that purpose withdrawn — the
    link in the newest mail is the only one that works."""
    lifetime: timedelta = INVITE_LIFETIME if purpose == Purpose.INVITE else RESET_LIFETIME
    accounts.withdraw(purpose, user_id=user.id)
    return accounts.issue(purpose, lifetime=lifetime, user_id=user.id)


def letter_for(
    user: User, purpose: Purpose, url: str, config: HeraConfig, *, inviter: str = ""
) -> Letter:
    instance = config.instance.name
    if purpose == Purpose.INVITE:
        return letters.invitation(to=user.email, instance=instance, inviter=inviter, url=url)
    return letters.reset(to=user.email, instance=instance, url=url)


def deliver(mailer: Mailer, config: HeraConfig, letter: Letter) -> tuple[bool, str]:
    """Send it if mail is set up. ``(mailed, why not)`` — never raises, because a link that did
    not go by mail is still a link somebody can copy."""
    if not config.mail.configured:
        return False, ""
    try:
        mailer.send(config.mail, letter, sender_name=config.instance.name)
    except MailError as exc:
        log.warning("mail to %s did not go: %s", letter.to, exc)
        return False, str(exc)
    return True, ""


def send(
    accounts: Accounts,
    mailer: Mailer,
    config: HeraConfig,
    user: User,
    *,
    base: str,
    commit: Callable[[], None],
    inviter: str = "",
    purpose: Purpose | None = None,
    by_mail: bool = True,
) -> Sent:
    """Make this person a link and mail it if possible — the whole of an invitation or an
    admin's reset link.

    ``commit`` runs between the two: a link in somebody's inbox has to work the moment it
    arrives, so the token is in the database before the mail server is even asked.

    ``by_mail=False`` is *copy a link*: made and handed back, not sent. It still replaces the
    one sent before — the stored token is a digest, so there is no earlier link to show again.
    """
    purpose = purpose or purpose_for(accounts, user)
    url = mail.link(base, issue(accounts, user, purpose))
    commit()
    if not by_mail:
        return Sent(link=url, mailed=False)
    mailed, error = deliver(mailer, config, letter_for(user, purpose, url, config, inviter=inviter))
    return Sent(link=url, mailed=mailed, mail_error=error)

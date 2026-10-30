"""Whether this instance has an owner yet, and the code that proves you may become it.

An instance nobody can sign in to is **unclaimed**, and shows the setup wizard. Exposed to a
network in that state, it belongs to whoever opens it first — so a fresh boot prints a setup code
to its log and writes it to ``~/.hera/setup-code``, and the wizard asks for it from anywhere
but the machine itself (ADR 27). Having read the log, or having a shell on the host, is the
credential.
"""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from uuid import UUID

from sqlmodel import Session

from hera_accounts import Accounts, Purpose, Role, User
from hera_home import setup_code_path
from hera_storage import Database

SETUP_LIFETIME = timedelta(days=7)
"""A boot prints a fresh one anyway; this only stops a code from a log nobody rotated working
forever."""

_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
"""No 0/O, 1/I/L: the code is read off a terminal and typed by hand."""


def unclaimed(session: Session) -> bool:
    return not Accounts(session).any_credential()


def new_setup_code() -> str:
    """Twelve characters in three groups — about 59 bits, behind a throttle, valid for days."""
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def normalise_code(code: str) -> str:
    """What a person typed, in the form it was issued: case and separators do not matter."""
    raw = "".join(ch for ch in code.upper() if ch.isalnum())
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}" if len(raw) == 12 else raw


def announce(database: Database) -> str | None:
    """Issue a setup code if the instance is unclaimed, and return it to be printed.

    Every earlier unspent code is withdrawn first, so the one in the log is the only one that
    works. A claimed instance gets ``None`` and loses any code file a previous boot left behind.
    """
    path = setup_code_path()
    with database.session() as session:
        if not unclaimed(session):
            path.unlink(missing_ok=True)
            return None
        accounts = Accounts(session)
        accounts.withdraw(Purpose.SETUP)
        code = accounts.issue(Purpose.SETUP, lifetime=SETUP_LIFETIME, token=new_setup_code())
        session.commit()

    path.parent.mkdir(parents=True, exist_ok=True)
    # Readable by the owner only, from the moment it exists: written through a descriptor opened
    # with the mode rather than chmod-ed afterwards.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(code + "\n")
    return code


def claimed(session: Session) -> None:
    """The instance has an admin now: no setup code may work again, and none is left on disk."""
    Accounts(session).withdraw(Purpose.SETUP)
    setup_code_path().unlink(missing_ok=True)


def claim_as_admin(
    session: Session, owner_id: UUID, *, email: str, name: str, password: str
) -> User:
    """Make the first admin, under the id every row of a single-user install already carries.

    An install from before accounts has a user row under that id already — migrated from the old
    account record, with no password — and it is *adopted*: the same row, now with an email to
    sign in with, a password and the admin role. A fresh install gets the row made. Either way
    every chat, project and profile there is is already theirs (ADR 27).
    """
    accounts = Accounts(session)
    existing = accounts.get(owner_id)
    if existing is None:
        user = accounts.create(
            email, name=name, role=Role.ADMIN, password=password, user_id=owner_id
        )
    else:
        user = accounts.update(existing, name=name or existing.name, email=email)
        user = accounts.set_role(user, Role.ADMIN)
        accounts.set_password(user.id, password)
        if user.disabled:
            accounts.set_disabled(user, False)
    claimed(session)
    return user

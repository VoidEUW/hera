"""The four tables: who someone is, how they prove it, where they are signed in, and what they
were handed once.

Every secret here is stored as a digest, never as itself. A password as argon2id, because it
is chosen by a person and short enough to guess at; a session or one-time token as SHA-256,
because it is 32 random bytes and nothing is gained by making a lookup slow.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field

from hera_storage import Entity, UTCDateTime

# SQLModel's `sa_type` wants an instance although the annotation says a type.
_TIMESTAMP: Any = UTCDateTime()


class Role(StrEnum):
    """Two, and no permission matrix (ADR 27). A third waits until somebody needs one."""

    ADMIN = "admin"
    USER = "user"


class Purpose(StrEnum):
    """What a one-time token is for. A token redeemed for the wrong purpose is not a token."""

    SETUP = "setup"
    """Printed to the server's log on a fresh install, so the first person to open an exposed
    server is not automatically its owner."""

    INVITE = "invite"
    RESET = "reset"
    LAUNCH = "launch"
    """Handed by the desktop app to the server it started, in place of a setup code."""


class User(Entity, table=True):
    """Somebody who can sign in, or could once they have a credential."""

    __tablename__ = "account_users"
    __table_args__ = (UniqueConstraint("email"), Index(None, "created_at", "id"))

    email: str
    """Stored lowercased, so ``Ana@Example.com`` and ``ana@example.com`` are one person."""

    name: str = ""
    role: str = Field(default=Role.USER)
    """A :class:`Role` value. A plain string column rather than a database enum, so a third
    role later is a new value and not a migration that rebuilds the table."""

    disabled: bool = False
    avatar_type: str = ""
    """The media type of the stored avatar, or empty when there is none. The bytes are a file."""


class Password(Entity, table=True):
    """At most one per user. Kept out of :class:`User` so that reading a user never reads a
    hash, and so a passkey-only account (M4) is simply a user with no row here."""

    __tablename__ = "account_passwords"
    __table_args__ = (UniqueConstraint("user_id"),)

    user_id: UUID = Field(index=True)
    hash: str


class Passkey(Entity, table=True):
    """A WebAuthn credential: a key pair whose private half never leaves the person's device.

    What is kept is the public half and the bookkeeping WebAuthn asks for — the credential's id,
    which the browser hands back to say which key it used, and the signature counter, which an
    authenticator that counts raises on every use so a cloned key shows up as a counter that went
    backwards. Both binary values are stored base64url-encoded, the form they travel in.
    """

    __tablename__ = "account_passkeys"
    __table_args__ = (UniqueConstraint("credential_id"),)

    user_id: UUID = Field(index=True)
    credential_id: str
    public_key: str
    """The COSE-encoded public key, base64url."""

    sign_count: int = 0
    transports: str = ""
    """How the authenticator was reached when it was registered — ``internal,hybrid`` — handed
    back to the browser later so it knows where to look. Comma-separated; a hint, not a rule."""

    label: str = ""
    """What its owner calls it: "MacBook", "phone". Defaults to when it was added."""

    last_used_at: datetime | None = Field(default=None, sa_type=_TIMESTAMP)


class SignIn(Entity, table=True):
    """One signed-in browser. Deleting the row is signing it out.

    Not called ``Session``: that word already means a database transaction in every module that
    would import this one.
    """

    __tablename__ = "account_sessions"
    __table_args__ = (UniqueConstraint("token_hash"),)

    user_id: UUID = Field(index=True)
    token_hash: str
    expires_at: datetime = Field(sa_type=_TIMESTAMP)
    last_seen_at: datetime = Field(sa_type=_TIMESTAMP)
    user_agent: str = ""


class OneTimeToken(Entity, table=True):
    """A secret that works once, for one purpose, until it expires."""

    __tablename__ = "account_tokens"
    __table_args__ = (UniqueConstraint("token_hash"),)

    purpose: str
    """A :class:`Purpose` value, plain for the reason :attr:`User.role` is."""

    token_hash: str
    user_id: UUID | None = Field(default=None, index=True)
    """Who it acts for, where that is known when it is issued: a reset is for somebody, a setup
    code is for whoever turns up with it."""

    expires_at: datetime = Field(sa_type=_TIMESTAMP)
    used_at: datetime | None = Field(default=None, sa_type=_TIMESTAMP)


ALL_TABLES = (User, Password, Passkey, SignIn, OneTimeToken)

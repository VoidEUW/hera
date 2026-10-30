"""Everything that is done to an account, over one database session.

Flushes and never commits: the caller owns the unit of work, so a sign-up that fails half-way
through — a user written, then a refused invite — leaves nothing behind.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import cache
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import func
from sqlmodel import Session, col, delete, select

from hera_accounts.models import OneTimeToken, Password, Purpose, Role, SignIn, User
from hera_storage import utcnow

SESSION_LIFETIME = timedelta(days=30)
"""How long a sign-in lasts without being used. Each use within it pushes the end back, so a
person who opens Hera every week is never asked again, and a laptop left in a drawer is."""

SEEN_GRANULARITY = timedelta(minutes=5)
"""How stale ``last_seen_at`` may get before a request writes it again. Every request is
authenticated, and a write per request is a write per streamed turn for nothing anyone reads
more precisely than this."""

MIN_PASSWORD = 8
MAX_PASSWORD = 1024
"""argon2 takes anything; a megabyte typed into the field is a request that costs the server a
megabyte of hashing, which is a cheaper way to make it busy than it should be."""

_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")
"""Something@somewhere.tld. Every dot in the domain is a separator, so the pattern can match an
address only one way; ``[^@\s]+\.[^@\s]+`` could match a dot as itself or as part of either
side, and backtracking through that is polynomial — a crafted address made it slow (CodeQL
``py/polynomial-redos``)."""


class AccountError(ValueError):
    """Something a person asked for that cannot be done. The message is for them."""


class EmailTaken(AccountError):
    pass


class LastAdmin(AccountError):
    """The change would leave nobody able to manage the instance."""


def new_token() -> str:
    """32 random bytes, URL-safe. The only form a session or one-time token ever leaves in."""
    return secrets.token_urlsafe(32)


def digest(token: str) -> str:
    """What is stored for a token. SHA-256, not argon2: the token is random, so there is
    nothing for a slow hash to protect, and every request looks one up."""
    return hashlib.sha256(token.encode()).hexdigest()


def normalise_email(email: str) -> str:
    """Lowercased and trimmed, or :class:`AccountError` for something that is not an address."""
    cleaned = email.strip().lower()
    if not _EMAIL.match(cleaned):
        raise AccountError("that is not an email address")
    return cleaned


def check_password(password: str) -> str:
    """The rule for a new password: long enough to not be a guess, short enough to hash."""
    if len(password) < MIN_PASSWORD:
        raise AccountError(f"a password needs at least {MIN_PASSWORD} characters")
    if len(password) > MAX_PASSWORD:
        raise AccountError(f"a password may not be longer than {MAX_PASSWORD} characters")
    return password


@cache
def _decoy(hasher: PasswordHasher) -> str:
    """A hash to verify against when the email is unknown, so an unknown email takes as long to
    refuse as a wrong password — otherwise the timing says which addresses have accounts."""
    return hasher.hash(secrets.token_hex(16))


class Accounts:
    """Users, credentials, sessions and one-time tokens."""

    def __init__(
        self,
        session: Session,
        *,
        hasher: PasswordHasher | None = None,
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._session = session
        self._hasher = hasher or DEFAULT_HASHER
        self._now = now

    # -- users ----------------------------------------------------------------------------------

    def get(self, user_id: UUID) -> User | None:
        return self._session.get(User, user_id)

    def by_email(self, email: str) -> User | None:
        cleaned = email.strip().lower()
        return self._session.exec(select(User).where(User.email == cleaned)).first()

    def users(self) -> list[User]:
        return list(self._session.exec(select(User).order_by(col(User.created_at), col(User.id))))

    def create(
        self,
        email: str,
        *,
        name: str = "",
        role: Role = Role.USER,
        password: str | None = None,
        user_id: UUID | None = None,
    ) -> User:
        """A new user, with a password if one is given. ``user_id`` is for the first admin, who
        takes the id every row of a single-user install already carries (ADR 27)."""
        address = normalise_email(email)
        if self.by_email(address) is not None:
            raise EmailTaken("there is already an account with that email")
        user = User(email=address, name=name.strip(), role=role)
        if user_id is not None:
            user.id = user_id
        self._session.add(user)
        self._session.flush()
        if password is not None:
            self.set_password(user.id, password)
        return user

    def update(self, user: User, *, name: str | None = None, email: str | None = None) -> User:
        if name is not None:
            user.name = name.strip()
        if email is not None:
            address = normalise_email(email)
            other = self.by_email(address)
            if other is not None and other.id != user.id:
                raise EmailTaken("there is already an account with that email")
            user.email = address
        user.updated_at = self._now()
        self._session.add(user)
        self._session.flush()
        return user

    def set_role(self, user: User, role: Role) -> User:
        if user.role == Role.ADMIN and role != Role.ADMIN:
            self._keep_an_admin(user)
        user.role = role
        user.updated_at = self._now()
        self._session.add(user)
        self._session.flush()
        return user

    def set_disabled(self, user: User, disabled: bool) -> User:
        """Disabling somebody signs them out everywhere; it does not delete anything of theirs."""
        if disabled and user.role == Role.ADMIN:
            self._keep_an_admin(user)
        user.disabled = disabled
        user.updated_at = self._now()
        self._session.add(user)
        if disabled:
            self.close_sessions(user.id)
        self._session.flush()
        return user

    def _keep_an_admin(self, leaving: User) -> None:
        others = self._session.exec(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.ADMIN, col(User.disabled).is_(False), User.id != leaving.id)
        ).one()
        if not others:
            raise LastAdmin("this is the only admin; make somebody else an admin first")

    # -- passwords ------------------------------------------------------------------------------

    def set_password(self, user_id: UUID, password: str) -> None:
        hashed = self._hasher.hash(check_password(password))
        existing = self._password(user_id)
        if existing is None:
            self._session.add(Password(user_id=user_id, hash=hashed))
        else:
            existing.hash = hashed
            existing.updated_at = self._now()
            self._session.add(existing)
        self._session.flush()

    def has_password(self, user_id: UUID) -> bool:
        return self._password(user_id) is not None

    def any_credential(self) -> bool:
        """Whether anybody can sign in at all. Until somebody can, the instance is unclaimed and
        the setup wizard is what it shows."""
        return self._session.exec(select(Password.id).limit(1)).first() is not None

    def verify(self, email: str, password: str) -> User | None:
        """The user these credentials belong to, or ``None`` — for an unknown email, a wrong
        password and a disabled account alike, in about the same time."""
        user = self.by_email(email)
        stored = self._password(user.id) if user is not None else None
        try:
            self._hasher.verify(
                stored.hash if stored is not None else _decoy(self._hasher), password
            )
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return None
        if user is None or stored is None or user.disabled:
            return None
        if self._hasher.check_needs_rehash(stored.hash):
            # Parameters raised since this was stored; the plaintext is in hand exactly now.
            stored.hash = self._hasher.hash(password)
            self._session.add(stored)
            self._session.flush()
        return user

    def _password(self, user_id: UUID) -> Password | None:
        return self._session.exec(select(Password).where(Password.user_id == user_id)).first()

    # -- sessions -------------------------------------------------------------------------------

    def open_session(
        self, user_id: UUID, *, user_agent: str = "", lifetime: timedelta = SESSION_LIFETIME
    ) -> tuple[str, SignIn]:
        """A new sign-in. The token is returned once and never stored."""
        token = new_token()
        now = self._now()
        sign_in = SignIn(
            user_id=user_id,
            token_hash=digest(token),
            expires_at=now + lifetime,
            last_seen_at=now,
            user_agent=user_agent[:300],
        )
        self._session.add(sign_in)
        self._session.flush()
        return token, sign_in

    def resolve(
        self, token: str, *, lifetime: timedelta = SESSION_LIFETIME
    ) -> tuple[User, SignIn] | None:
        """Who a session token belongs to, or ``None``. Using a session extends it."""
        if not token:
            return None
        sign_in = self._session.exec(
            select(SignIn).where(SignIn.token_hash == digest(token))
        ).first()
        if sign_in is None:
            return None
        now = self._now()
        if sign_in.expires_at <= now:
            self._session.delete(sign_in)
            self._session.flush()
            return None
        user = self.get(sign_in.user_id)
        if user is None or user.disabled:
            return None
        if now - sign_in.last_seen_at >= SEEN_GRANULARITY:
            sign_in.last_seen_at = now
            sign_in.expires_at = now + lifetime
            self._session.add(sign_in)
            self._session.flush()
        return user, sign_in

    def close_session(self, token: str) -> None:
        self._session.exec(delete(SignIn).where(col(SignIn.token_hash) == digest(token)))
        self._session.flush()

    def close_sessions(self, user_id: UUID, *, keep: UUID | None = None) -> int:
        """Sign somebody out everywhere — or everywhere but ``keep``, the browser asking."""
        statement = delete(SignIn).where(col(SignIn.user_id) == user_id)
        if keep is not None:
            statement = statement.where(col(SignIn.id) != keep)
        result = self._session.exec(statement)
        self._session.flush()
        return int(result.rowcount)

    def sessions(self, user_id: UUID) -> list[SignIn]:
        now = self._now()
        return list(
            self._session.exec(
                select(SignIn)
                .where(SignIn.user_id == user_id, SignIn.expires_at > now)
                .order_by(col(SignIn.last_seen_at).desc())
            )
        )

    def revoke(self, user_id: UUID, sign_in_id: UUID) -> bool:
        """Sign out one of *this user's* sessions. Somebody else's id is simply not found."""
        sign_in = self._session.get(SignIn, sign_in_id)
        if sign_in is None or sign_in.user_id != user_id:
            return False
        self._session.delete(sign_in)
        self._session.flush()
        return True

    # -- one-time tokens ------------------------------------------------------------------------

    def issue(
        self,
        purpose: Purpose,
        *,
        lifetime: timedelta,
        user_id: UUID | None = None,
        token: str | None = None,
    ) -> str:
        """A new token, returned once. ``token`` is for a caller that needs a shape a person can
        type — a setup code read off a log — rather than 43 URL-safe characters."""
        token = token if token is not None else new_token()
        self._session.add(
            OneTimeToken(
                purpose=purpose,
                token_hash=digest(token),
                user_id=user_id,
                expires_at=self._now() + lifetime,
            )
        )
        self._session.flush()
        return token

    def redeem(self, purpose: Purpose, token: str) -> OneTimeToken | None:
        """Spend a token. ``None`` for one that is unknown, used, expired or for something else."""
        if not token:
            return None
        found = self._session.exec(
            select(OneTimeToken).where(OneTimeToken.token_hash == digest(token))
        ).first()
        now = self._now()
        if (
            found is None
            or not hmac.compare_digest(found.purpose, purpose)
            or found.used_at is not None
            or found.expires_at <= now
        ):
            return None
        found.used_at = now
        self._session.add(found)
        self._session.flush()
        return found

    def withdraw(self, purpose: Purpose) -> int:
        """Delete every unspent token of one purpose — a setup code printed by a previous boot
        should not still work after this one printed another."""
        result = self._session.exec(
            delete(OneTimeToken).where(
                col(OneTimeToken.purpose) == purpose, col(OneTimeToken.used_at).is_(None)
            )
        )
        self._session.flush()
        return int(result.rowcount)


DEFAULT_HASHER = PasswordHasher()
"""argon2id with the library's defaults, which follow RFC 9106's second recommendation."""

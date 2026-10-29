"""Turning an HTTP request into a person (ADR 27).

``hera_accounts`` knows sessions and tokens and nothing about HTTP; this module is the other
half — the cookie a token travels in, the Origin check that stands in for a CSRF token, whether
a request is from the machine Hera runs on, and the backoff on guessing a password.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from ipaddress import ip_address
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import HTTPException, Request, Response, status
from sqlmodel import Session

from hera_accounts import SESSION_LIFETIME, Accounts, User
from hera_core.config import load as load_config
from hera_profiles import ProfileRepository

SESSION_COOKIE = "hera_session"

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

FORWARDING_HEADERS = ("forwarded", "x-forwarded-for", "x-real-ip")
"""Headers a reverse proxy adds. A request carrying one came *through* something, so a loopback
peer address says where the proxy is and nothing about where the person is."""


@dataclass(frozen=True)
class Viewer:
    """Who a request is from: their id, their role, and which sign-in it came through."""

    id: UUID
    role: str
    session_id: UUID

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def session_token(request: Request) -> str:
    return request.cookies.get(SESSION_COOKIE, "")


def _secure(request: Request) -> bool:
    """Whether the browser reached this over https — directly, or as the public URL says."""
    return request.url.scheme == "https" or load_config().instance.public_url.startswith("https:")


def set_session_cookie(
    response: Response, request: Request, token: str, *, lifetime: timedelta
) -> None:
    """HttpOnly so a script cannot read it, ``Lax`` so another site cannot send it with a form,
    and ``Secure`` whenever the browser is on https."""
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(lifetime.total_seconds()),
        path="/",
        httponly=True,
        samesite="lax",
        secure=_secure(request),
    )


def sign_in_as(session: Session, request: Request, response: Response, user: User) -> None:
    """Sign this browser in as ``user``, replacing whatever session it was carrying.

    Commits before it returns: the browser sends the cookie back on its very next request, and
    the row behind it has to be there by then — teardown commits only after the response left.

    Also makes sure the person has a profile to be answered as. Boot makes one for the first
    admin; somebody who registered, or was made with ``hera user create``, gets theirs here, the
    first time they arrive.
    """
    ProfileRepository(session).ensure_default_exists(user.id)
    accounts = Accounts(session)
    previous = session_token(request)
    if previous:
        accounts.close_session(previous)
    token, _ = accounts.open_session(user.id, user_agent=request.headers.get("user-agent", ""))
    session.commit()
    set_session_cookie(response, request, token, lifetime=SESSION_LIFETIME)


def clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=_secure(request)
    )


def is_loopback(request: Request) -> bool:
    """Whether the request comes from the machine Hera runs on, and not through a proxy there.

    The second half matters: a reverse proxy on the same host makes *every* visitor's peer
    address 127.0.0.1, and a setup wizard that trusted that would hand the instance to the
    first stranger who found it.
    """
    if any(header in request.headers for header in FORWARDING_HEADERS):
        return False
    host = request.client.host if request.client else ""
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


def same_origin(request: Request) -> None:
    """Refuse an unsafe request a browser sent from another site — the CSRF check.

    ``SameSite=Lax`` already keeps the cookie off most of those; this closes the rest, including
    a sibling subdomain, which is *same-site* and so does get the cookie. A request with no
    ``Origin`` at all is not from a browser doing something on another page's behalf — browsers
    send one with every cross-origin unsafe request — so a script or the CLI is not turned away.
    """
    if request.method not in UNSAFE_METHODS:
        return
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise _cross_origin()
    origin = request.headers.get("origin")
    if origin is None:
        return
    if origin != "null" and urlsplit(origin).netloc == request.headers.get("host", ""):
        return
    public = load_config().instance.public_url
    if public and origin.rstrip("/") == public:
        return
    raise _cross_origin()


def _cross_origin() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="that request came from another site"
    )


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@dataclass
class Throttle:
    """Backoff on failed guesses, in memory, per key.

    A few mistakes are free; after that each one doubles the wait before the next attempt counts,
    up to a ceiling. Keyed by address *and* by email, so neither one machine trying many
    accounts nor many machines trying one account gets far. In memory because it only has to
    outlast an attack, not a restart.
    """

    free: int = 5
    ceiling: float = 15 * 60
    clock: Callable[[], float] = time.monotonic
    _failures: dict[str, tuple[int, float]] = field(default_factory=dict)

    def wait(self, *keys: str) -> float:
        """Seconds before another attempt on any of these keys will be heard; 0 if now."""
        now = self.clock()
        longest = 0.0
        for key in keys:
            count, last = self._failures.get(key, (0, 0.0))
            if count >= self.free:
                delay = min(self.ceiling, 2.0 ** (count - self.free))
                longest = max(longest, last + delay - now)
        return longest

    def failed(self, *keys: str) -> None:
        now = self.clock()
        if len(self._failures) > 10_000:
            self._forget_older_than(now - self.ceiling)
        for key in keys:
            count, _ = self._failures.get(key, (0, 0.0))
            self._failures[key] = (count + 1, now)

    def succeeded(self, *keys: str) -> None:
        for key in keys:
            self._failures.pop(key, None)

    def check(self, *keys: str) -> None:
        """Raise a 429 saying how long to wait, if any of these keys has to."""
        remaining = self.wait(*keys)
        if remaining > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too many attempts; wait a moment and try again",
                headers={"Retry-After": str(max(1, round(remaining)))},
            )

    def _forget_older_than(self, cutoff: float) -> None:
        for key in [key for key, (_, last) in self._failures.items() if last < cutoff]:
            del self._failures[key]

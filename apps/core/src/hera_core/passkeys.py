"""Passkeys: the WebAuthn ceremonies around what ``hera_accounts`` keeps (ADR 27, M4).

A ceremony is two requests. The first hands the browser options with a random challenge; the
second brings back what the authenticator signed over it, and is verified against that challenge,
this site's origin and — to sign in — the public key stored when the passkey was registered. The
challenge has to be remembered between the two, and it is, here, in memory: it is worth a few
minutes, only to this server process, and a restart costing somebody one retry is cheaper than a
table for it.

**Which site a passkey belongs to** (the *relying party*) is a domain name, so a passkey made at
``hera.example.com`` works there and nowhere else. It is the public URL's host when one is set,
or the host this browser used. WebAuthn refuses two things outright, and they decide whether
passkeys are offered at all: an IP address as the relying party, and a page that is not a secure
context — ``https``, or ``localhost``. A Hera opened at ``http://192.168.1.20:8756`` has
neither, and is offered passwords only.

Passkeys are *discoverable* (resident keys): the authenticator remembers which account a key is
for, so signing in needs no email typed first — the browser lists the keys it has for this site.
"""

from __future__ import annotations

import ipaddress
import secrets
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Request
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json_dict
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from hera_accounts import Passkey, User
from hera_core.addresses import is_loopback
from hera_core.config import HeraConfig

CEREMONY_LIFETIME_S = 300.0
"""How long a browser has between asking for options and answering them. A person may have to
find their phone."""

TRANSPORTS = frozenset(item.value for item in AuthenticatorTransport)


class PasskeyError(ValueError):
    """The ceremony failed. The message is for the person, not a WebAuthn error name."""


@dataclass(frozen=True)
class RelyingParty:
    id: str
    """The domain a passkey is bound to."""
    origin: str
    """The exact origin the browser's signed data has to name — scheme, host and port."""
    name: str


def relying_party(request: Request, config: HeraConfig) -> RelyingParty | None:
    """Who passkeys belong to for this request, or ``None`` when WebAuthn cannot work here.

    With a public URL, only a browser that is actually *at* it gets one: a passkey registered for
    ``hera.example.com`` from a page at ``localhost`` is something the browser itself refuses.
    """
    page = urlsplit(str(request.base_url))
    public = config.instance.public_url
    if public:
        site = urlsplit(public)
        if (site.hostname or "") != (page.hostname or ""):
            return None
    else:
        site = page
    host = site.hostname or ""
    if not host or _is_ip(host):
        return None
    if site.scheme != "https" and not is_loopback(host):
        return None
    return RelyingParty(
        id=host, origin=f"{site.scheme}://{site.netloc}", name=config.instance.name or "Hera"
    )


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


# -- the remembered challenges --------------------------------------------------------------------


@dataclass(frozen=True)
class Ceremony:
    challenge: bytes
    rp: RelyingParty
    user_id: UUID | None
    """Whose registration this is; ``None`` for signing in, where nobody is known yet."""
    expires: float


@dataclass
class Ceremonies:
    """Challenges handed out and not yet answered, each good once and for a few minutes."""

    clock: Any = time.monotonic
    _open: dict[str, Ceremony] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def begin(self, challenge: bytes, rp: RelyingParty, user_id: UUID | None) -> str:
        key = secrets.token_urlsafe(24)
        now = self.clock()
        with self._lock:
            for stale in [k for k, c in self._open.items() if c.expires <= now]:
                del self._open[stale]
            self._open[key] = Ceremony(challenge, rp, user_id, now + CEREMONY_LIFETIME_S)
        return key

    def finish(self, key: str, *, user_id: UUID | None) -> Ceremony:
        """The ceremony, spent — or :class:`PasskeyError` for one that is unknown, expired, or
        begun by somebody else."""
        with self._lock:
            found = self._open.pop(key, None)
        if found is None or found.expires <= self.clock() or found.user_id != user_id:
            raise PasskeyError("that took too long, or was already used; try again")
        return found


# -- registering ----------------------------------------------------------------------------------


def registration_options(
    rp: RelyingParty, user: User, existing: list[Passkey]
) -> tuple[bytes, dict[str, Any]]:
    """The challenge and the options for ``navigator.credentials.create``. A key this person
    already registered is excluded, so the same authenticator is not added twice."""
    options = generate_registration_options(
        rp_id=rp.id,
        rp_name=rp.name,
        user_id=user.id.bytes,
        user_name=user.email,
        user_display_name=user.name or user.email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[_descriptor(passkey) for passkey in existing],
    )
    return options.challenge, options_to_json_dict(options)


@dataclass(frozen=True)
class Registered:
    credential_id: str
    public_key: str
    sign_count: int
    transports: list[str]


def verify_registration(ceremony: Ceremony, credential: Mapping[str, Any]) -> Registered:
    try:
        verified = verify_registration_response(
            credential=dict(credential),
            expected_challenge=ceremony.challenge,
            expected_origin=ceremony.rp.origin,
            expected_rp_id=ceremony.rp.id,
        )
    except (WebAuthnException, ValueError, KeyError, TypeError):
        raise PasskeyError("this passkey could not be verified; try again") from None
    response = credential.get("response")
    offered = response.get("transports", []) if isinstance(response, Mapping) else []
    return Registered(
        credential_id=bytes_to_base64url(verified.credential_id),
        public_key=bytes_to_base64url(verified.credential_public_key),
        sign_count=verified.sign_count,
        transports=[str(item) for item in offered if item in TRANSPORTS],
    )


# -- signing in -----------------------------------------------------------------------------------


def authentication_options(rp: RelyingParty) -> tuple[bytes, dict[str, Any]]:
    """Options for ``navigator.credentials.get`` with no credentials listed: the browser offers
    whichever passkeys it holds for this site, and the one chosen says whose it is."""
    options = generate_authentication_options(
        rp_id=rp.id, user_verification=UserVerificationRequirement.PREFERRED
    )
    return options.challenge, options_to_json_dict(options)


def credential_id_of(credential: Mapping[str, Any]) -> str:
    """Which key the browser says it used — to look it up before it is checked."""
    raw = credential.get("rawId") or credential.get("id")
    if not isinstance(raw, str) or not raw:
        raise PasskeyError("this passkey could not be verified; try again")
    return raw


def verify_authentication(
    ceremony: Ceremony, credential: Mapping[str, Any], passkey: Passkey
) -> int:
    """The new signature counter, once the signature is the stored key's over this challenge."""
    try:
        verified = verify_authentication_response(
            credential=dict(credential),
            expected_challenge=ceremony.challenge,
            expected_rp_id=ceremony.rp.id,
            expected_origin=ceremony.rp.origin,
            credential_public_key=base64url_to_bytes(passkey.public_key),
            credential_current_sign_count=passkey.sign_count,
        )
    except (WebAuthnException, ValueError, KeyError, TypeError):
        raise PasskeyError("that passkey could not sign you in") from None
    return int(verified.new_sign_count)


def _descriptor(passkey: Passkey) -> PublicKeyCredentialDescriptor:
    transports = [
        AuthenticatorTransport(item) for item in passkey.transports.split(",") if item in TRANSPORTS
    ]
    return PublicKeyCredentialDescriptor(
        id=base64url_to_bytes(passkey.credential_id), transports=transports or None
    )

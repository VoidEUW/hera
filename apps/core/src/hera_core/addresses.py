"""Which address somebody *else* can reach this Hera at.

``hera serve --host 0.0.0.0`` means *listen on every interface*. A browser on the same machine
can open ``http://0.0.0.0:8756`` and get an answer, and that is the trap: the admin then copies an
invitation built from the address their own browser used, and the person it goes to opens a link
that points at their own computer. ``localhost`` and ``127.0.0.1`` have the same problem.

So a link is rewritten before it is handed out. An address only the machine itself can use
becomes one other machines can — this machine's LAN address when Hera listens on every
interface, or the specific address it was bound to. A server bound to loopback alone is
reachable from nowhere else, and its links say so honestly by staying local.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

UNSPECIFIED = frozenset({"0.0.0.0", "::", ""})
"""What *every interface* is spelled as. A place to listen, never an address to open."""

_PROBE = ("192.0.2.1", 9)
"""TEST-NET-1 (RFC 5737): never routed anywhere. Connecting a UDP socket to it sends nothing and
only asks the system which local address it *would* use, which is the LAN address."""


def is_unspecified(host: str) -> bool:
    return host.strip("[]") in UNSPECIFIED


def is_loopback(host: str) -> bool:
    bare = host.strip("[]").lower()
    if bare == "localhost" or bare.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(bare).is_loopback
    except ValueError:
        return False


def lan_address() -> str | None:
    """This machine's address on its network, or ``None`` when it has none worth naming."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(_PROBE)
            found = str(probe.getsockname()[0])
    except OSError:
        return None
    return None if is_unspecified(found) or is_loopback(found) else found


def reachable_from(bind_host: str) -> str:
    """The host another machine would use for a server bound to ``bind_host``."""
    if is_unspecified(bind_host):
        return lan_address() or "127.0.0.1"
    if is_loopback(bind_host):
        return "127.0.0.1"
    return bind_host


def reachable_base(base: str, *, bind_host: str) -> str:
    """``base`` with a host only this machine can use replaced by one others can.

    A real name or address — ``hera.example.com``, ``192.168.1.20`` — is kept as it is: it is
    what the asking browser reached the server at, so it works at least from there.
    """
    parts = urlsplit(base.rstrip("/"))
    host = parts.hostname or ""
    if not (is_unspecified(host) or is_loopback(host)):
        return base.rstrip("/")
    if is_loopback(host) and is_loopback(bind_host):
        return base.rstrip("/")
    replacement = reachable_from(bind_host)
    if ":" in replacement:
        replacement = f"[{replacement}]"
    netloc = f"{replacement}:{parts.port}" if parts.port else replacement
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))

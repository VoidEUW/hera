"""Helpers the application suite imports by name.

Not in `conftest.py`: mypy is configured to skip those, because two packages' conftests resolve
to one module name and it has no by-path loading the way pytest does.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from httpx import AsyncClient, Response

from hera_permissions import Decision, Outcome, Policy
from hera_tools import Catalogue, Failure, Tool, ToolInvocation, ToolResult

API = "/api/v1"
"""The versioned prefix every route sits under (ADR 6)."""


def sign_in(http: AsyncClient, services: Any, user_id: Any = None) -> AsyncClient:
    """Sign a hand-built client in — as the first admin unless ``user_id`` says otherwise.

    ``services`` is a ``hera_core.wiring.Services``; typed loosely so this module does not import
    the application at collection time.
    """
    from hera_accounts import Accounts
    from hera_core.auth import SESSION_COOKIE

    with services.database.session() as session:
        token, _ = Accounts(session).open_session(user_id or services.settings.owner_id)
    http.cookies.set(SESSION_COOKIE, token, domain="hera.test")
    return http


def unclaim(database: Any) -> None:
    """Back to an install nobody can sign in to: the owner's row stays, its password goes."""
    from sqlmodel import delete

    from hera_accounts import Password

    with database.session() as session:
        session.exec(delete(Password))


OWNER_EMAIL = "owner@hera.test"
OWNER_PASSWORD = "correct horse battery"
"""The first admin every application test runs as. Created by `make_services`."""


class WriteSkill(Protocol):
    """Writes a skill directory under the temporary skills path and returns it."""

    def __call__(self, skill_id: str, *, description: str = ..., body: str = ...) -> Path: ...


class StubTools:
    """A tool layer with scripted answers, satisfying ``hera_chats.ports.Tools``."""

    def __init__(
        self,
        *,
        tools: Sequence[str] = ("fs__read_file",),
        policy: Policy | None = None,
    ) -> None:
        self.catalogue_value = Catalogue.of(
            Tool(
                name=name,
                server=name.split("__")[0],
                local_name=name.split("__")[-1],
                description=f"does {name}",
            )
            for name in tools
        )
        self._policy = policy or Policy(fallback=Decision.ALLOW)
        self.dispatched: list[list[ToolInvocation]] = []
        self.context_seen: list[Mapping[str, str] | None] = []

    @property
    def policy(self) -> Policy:
        return self._policy

    def with_policy(self, policy: Policy) -> StubTools:
        replacement = StubTools(policy=policy)
        replacement.catalogue_value = self.catalogue_value
        replacement.dispatched = self.dispatched
        replacement.context_seen = self.context_seen
        return replacement

    def check(self, tool: str, *, profile: str | None = None) -> Outcome:
        return self._policy.check(tool, profile=profile)

    async def catalogue(self, *, refresh: bool = False) -> Catalogue:
        return self.catalogue_value

    async def status(self) -> tuple[Any, ...]:
        from hera_tools import ServerStatus

        return (ServerStatus(name="fs", connected=True, tools=len(self.catalogue_value)),)

    async def dispatch_all(
        self,
        invocations: Iterable[ToolInvocation],
        *,
        profile: str | None = None,
        confirmed: Sequence[str] = (),
        context: Mapping[str, str] | None = None,
    ) -> list[ToolResult]:
        calls = list(invocations)
        self.dispatched.append(calls)
        self.context_seen.append(context)
        return [self._answer(call) for call in calls]

    async def aclose(self) -> None:
        return None

    def _answer(self, call: ToolInvocation) -> ToolResult:
        outcome = self._policy.check(call.tool)
        if outcome.decision is Decision.DENY:
            return ToolResult.failed(
                call_id=call.call_id,
                tool=call.tool,
                failure=Failure.DENIED,
                text=f"not allowed — {outcome.reason}",
            )
        return ToolResult(call_id=call.call_id, tool=call.tool, text=f"ran {call.tool}")


def sse(response: Response) -> list[tuple[str, Any]]:
    """Parse a Server-Sent Events body into ``(event name, payload)`` pairs.

    Written out rather than pulled from a library because it is the thing under test: if the
    framing is wrong, a parser that is lenient about it would hide exactly the bug worth
    catching.
    """
    frames: list[tuple[str, Any]] = []
    for block in response.text.split("\n\n"):
        if not block.strip():
            continue
        name = ""
        data: list[str] = []
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data.append(line.removeprefix("data: "))
        frames.append((name, json.loads("\n".join(data))))
    return frames


def names(frames: Sequence[tuple[str, Any]]) -> list[str]:
    return [name for name, _ in frames]


def payload(frames: Sequence[tuple[str, Any]], name: str) -> Any:
    """The first payload of one event name."""
    for found, body in frames:
        if found == name:
            return body
    raise AssertionError(f"no {name!r} frame in {names(frames)}")


class SoftAuthenticator:
    """A passkey authenticator in software: a P-256 key that builds and signs exactly what a real
    one does (WebAuthn §6.1, attestation ``none``), so the server verifies it as it would a phone.

    ``origin`` is the page the browser would be on — what lands in the signed client data.
    """

    def __init__(self, origin: str = "https://hera.test") -> None:
        import secrets

        from cryptography.hazmat.primitives.asymmetric import ec

        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = secrets.token_bytes(16)
        self.count = 0
        self.user_handle = b""

    def create(self, options: dict[str, Any]) -> dict[str, Any]:
        """``navigator.credentials.create``, answered."""
        import cbor2
        from webauthn.helpers import base64url_to_bytes

        self.user_handle = base64url_to_bytes(options["user"]["id"])
        client = self._client("webauthn.create", options["challenge"])
        attested = (
            bytes(16)  # aaguid: an authenticator that does not say what it is
            + len(self.credential_id).to_bytes(2, "big")
            + self.credential_id
            + self._cose()
        )
        data = self._rp_hash(options["rp"]["id"]) + bytes([0x45]) + self.count.to_bytes(4, "big")
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": data + attested})
        return self._credential(
            {
                "clientDataJSON": _b64(client),
                "attestationObject": _b64(attestation),
                "transports": ["internal", "made-up"],
            }
        )

    def get(self, options: dict[str, Any], *, count: int | None = None) -> dict[str, Any]:
        """``navigator.credentials.get``, answered — signed, with the counter raised."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        self.count = count if count is not None else self.count + 1
        client = self._client("webauthn.get", options["challenge"])
        data = self._rp_hash(options["rpId"]) + bytes([0x05]) + self.count.to_bytes(4, "big")
        signed = data + hashlib.sha256(client).digest()
        signature = self.key.sign(signed, ec.ECDSA(hashes.SHA256()))
        return self._credential(
            {
                "clientDataJSON": _b64(client),
                "authenticatorData": _b64(data),
                "signature": _b64(signature),
                "userHandle": _b64(self.user_handle),
            }
        )

    def _client(self, kind: str, challenge: str) -> bytes:
        return json.dumps(
            {"type": kind, "challenge": challenge, "origin": self.origin, "crossOrigin": False}
        ).encode()

    def _rp_hash(self, rp_id: str) -> bytes:
        return hashlib.sha256(rp_id.encode()).digest()

    def _cose(self) -> bytes:
        import cbor2

        numbers = self.key.public_key().public_numbers()
        return bytes(
            cbor2.dumps(
                {
                    1: 2,  # kty: EC2
                    3: -7,  # alg: ES256
                    -1: 1,  # crv: P-256
                    -2: numbers.x.to_bytes(32, "big"),
                    -3: numbers.y.to_bytes(32, "big"),
                }
            )
        )

    def _credential(self, response: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _b64(self.credential_id),
            "rawId": _b64(self.credential_id),
            "type": "public-key",
            "response": response,
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }


def _b64(raw: bytes) -> str:
    from webauthn.helpers import bytes_to_base64url

    return str(bytes_to_base64url(raw))

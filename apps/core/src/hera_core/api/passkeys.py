"""Passkeys: adding one on Settings → Account, and signing in with one (ADR 27, M4).

Each act is two requests — options, then the browser's answer — and both halves live here. The
ceremony itself is ``hera_core.passkeys``; what it proved is kept by ``hera_accounts``.

Signing in is public and is the sign-in card's other door, with the same answer for a key this
Hera does not know and a key that did not sign: telling them apart says which passkeys exist.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status

from hera_accounts import AccountError, Accounts
from hera_core import passkeys
from hera_core.auth import client_key, sign_in_as
from hera_core.config import load as load_config
from hera_core.deps import Container, Db, SignedIn, not_found
from hera_core.passkeys import PasskeyError, RelyingParty
from hera_core.schemas import (
    AccountOut,
    CeremonyOut,
    PasskeyIn,
    PasskeyOut,
    PasskeyPatch,
    PasskeySignInIn,
)

public = APIRouter(tags=["passkeys"])
router = APIRouter(tags=["passkeys"])


@router.get("/auth/passkeys", response_model=list[PasskeyOut])
def list_passkeys(viewer: SignedIn, db: Db) -> list[PasskeyOut]:
    return [PasskeyOut.of(item) for item in Accounts(db).passkeys(viewer.id)]


@router.post("/auth/passkeys/options", response_model=CeremonyOut)
def registration_options(
    viewer: SignedIn, request: Request, container: Container, db: Db
) -> CeremonyOut:
    accounts = Accounts(db)
    user = accounts.get(viewer.id)
    if user is None:  # pragma: no cover - a signed-in viewer has a row
        raise not_found("user")
    rp = _relying_party(request)
    challenge, options = passkeys.registration_options(rp, user, accounts.passkeys(user.id))
    return CeremonyOut(ceremony=container.ceremonies.begin(challenge, rp, user.id), options=options)


@router.post("/auth/passkeys", response_model=PasskeyOut, status_code=status.HTTP_201_CREATED)
def add_passkey(payload: PasskeyIn, viewer: SignedIn, container: Container, db: Db) -> PasskeyOut:
    accounts = Accounts(db)
    try:
        ceremony = container.ceremonies.finish(payload.ceremony, user_id=viewer.id)
        registered = passkeys.verify_registration(ceremony, payload.credential)
        added = accounts.add_passkey(
            viewer.id,
            credential_id=registered.credential_id,
            public_key=registered.public_key,
            sign_count=registered.sign_count,
            transports=registered.transports,
            label=payload.label or f"Passkey {len(accounts.passkeys(viewer.id)) + 1}",
        )
    except (PasskeyError, AccountError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return PasskeyOut.of(added)


@router.patch("/auth/passkeys/{passkey_id}", response_model=PasskeyOut)
def rename_passkey(passkey_id: UUID, payload: PasskeyPatch, viewer: SignedIn, db: Db) -> PasskeyOut:
    renamed = Accounts(db).rename_passkey(viewer.id, passkey_id, payload.label)
    if renamed is None:
        raise not_found("passkey")
    return PasskeyOut.of(renamed)


@router.delete("/auth/passkeys/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_passkey(passkey_id: UUID, viewer: SignedIn, db: Db) -> None:
    if not Accounts(db).remove_passkey(viewer.id, passkey_id):
        raise not_found("passkey")


@public.post("/auth/passkey/options", response_model=CeremonyOut)
def sign_in_options(request: Request, container: Container) -> CeremonyOut:
    rp = _relying_party(request)
    challenge, options = passkeys.authentication_options(rp)
    return CeremonyOut(ceremony=container.ceremonies.begin(challenge, rp, None), options=options)


@public.post("/auth/passkey", response_model=AccountOut)
def sign_in_with_passkey(
    payload: PasskeySignInIn, request: Request, response: Response, container: Container, db: Db
) -> AccountOut:
    key = f"passkey:{client_key(request)}"
    container.throttle.check(key)
    accounts = Accounts(db)
    try:
        ceremony = container.ceremonies.finish(payload.ceremony, user_id=None)
        stored = accounts.passkey(passkeys.credential_id_of(payload.credential))
        user = accounts.get(stored.user_id) if stored is not None else None
        if stored is None or user is None or user.disabled:
            raise PasskeyError("that passkey could not sign you in")
        count = passkeys.verify_authentication(ceremony, payload.credential, stored)
    except PasskeyError as exc:
        container.throttle.failed(key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from None
    container.throttle.succeeded(key)
    accounts.used_passkey(stored, count)
    sign_in_as(db, request, response, user)
    return AccountOut.of(user)


def _relying_party(request: Request) -> RelyingParty:
    rp = passkeys.relying_party(request, load_config())
    if rp is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="passkeys need this Hera to be opened by name, over https or on localhost",
        )
    return rp

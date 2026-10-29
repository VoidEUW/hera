"""Signing in, signing out, registering, and the sessions a person has open (ADR 27).

Public where it has to be — the sign-in screen is drawn before anybody is signed in — and every
route that sets a cookie **commits before it returns**: the session row has to exist by the time
the browser sends the cookie back, and teardown runs after the response is on its way.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status

from hera_accounts import AccountError, Accounts, EmailTaken, Purpose
from hera_core.auth import clear_session_cookie, client_key, session_token, sign_in_as
from hera_core.claim import unclaimed
from hera_core.config import load as load_config
from hera_core.deps import Container, Db, SignedIn
from hera_core.schemas import (
    AccountOut,
    AuthStateOut,
    PasswordIn,
    RegisterIn,
    SessionOut,
    SignInIn,
)

router = APIRouter(tags=["auth"])


@router.get("/auth/state", response_model=AuthStateOut)
def auth_state(request: Request, db: Db) -> AuthStateOut:
    """Who is signed in, if anybody, and what the sign-in screen should offer."""
    found = Accounts(db).resolve(session_token(request))
    instance = load_config().instance
    return AuthStateOut(
        user=AccountOut.of(found[0]) if found is not None else None,
        setup_required=unclaimed(db),
        registration=instance.registration,
        instance_name=instance.name,
    )


@router.post("/auth/sign-in", response_model=AccountOut)
def sign_in(
    payload: SignInIn, request: Request, response: Response, container: Container, db: Db
) -> AccountOut:
    """One answer for an unknown email, a wrong password and a disabled account: telling them
    apart would tell a stranger which addresses have accounts here."""
    keys = (f"ip:{client_key(request)}", f"email:{payload.email.strip().lower()}")
    container.throttle.check(*keys)
    user = Accounts(db).verify(payload.email, payload.password)
    if user is None:
        container.throttle.failed(*keys)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="that email and password do not match an account here",
        )
    container.throttle.succeeded(*keys)
    sign_in_as(db, request, response, user)
    return AccountOut.of(user)


@router.post("/auth/sign-out", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(request: Request, response: Response, db: Db) -> None:
    """Ends this browser's session. Public and idempotent: signing out twice is not an error."""
    Accounts(db).close_session(session_token(request))
    db.commit()
    clear_session_cookie(response, request)


@router.post("/auth/register", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, request: Request, response: Response, db: Db) -> AccountOut:
    """A new account, as the instance's registration setting allows."""
    if unclaimed(db):
        # The first account is an admin and is made by the setup wizard, which asks for the
        # setup code. Registration must not be a way round it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="this Hera has not been set up yet"
        )
    accounts = Accounts(db)
    mode = load_config().instance.registration
    if mode == "closed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="registration is closed here; ask an admin for an account",
        )
    if mode == "invite" and accounts.redeem(Purpose.INVITE, payload.invite) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="registering here needs an invitation, and that one does not work",
        )
    try:
        user = accounts.create(payload.email, name=payload.name, password=payload.password)
    except EmailTaken as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except AccountError as exc:
        raise _unprocessable(exc) from None
    response.status_code = status.HTTP_201_CREATED
    sign_in_as(db, request, response, user)
    return AccountOut.of(user)


@router.get("/auth/sessions", response_model=list[SessionOut])
def list_sessions(viewer: SignedIn, db: Db) -> list[SessionOut]:
    return [
        SessionOut.of(row, current=viewer.session_id) for row in Accounts(db).sessions(viewer.id)
    ]


@router.delete("/auth/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: UUID, viewer: SignedIn, request: Request, response: Response, db: Db
) -> None:
    if not Accounts(db).revoke(viewer.id, session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such session")
    db.commit()
    if session_id == viewer.session_id:
        clear_session_cookie(response, request)


@router.delete("/auth/sessions", status_code=status.HTTP_204_NO_CONTENT)
def sign_out_everywhere(viewer: SignedIn, request: Request, response: Response, db: Db) -> None:
    """Every browser this person is signed in on, this one included."""
    Accounts(db).close_sessions(viewer.id)
    db.commit()
    clear_session_cookie(response, request)


@router.put("/auth/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordIn, viewer: SignedIn, request: Request, container: Container, db: Db
) -> None:
    """A new password, given the current one. Every *other* browser is signed out: a password
    is usually changed because somebody else might know the old one."""
    key = f"password:{viewer.id}"
    container.throttle.check(key)
    accounts = Accounts(db)
    user = accounts.get(viewer.id)
    if user is None or accounts.verify(user.email, payload.current) is None:
        container.throttle.failed(key)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="the current password is not right"
        )
    container.throttle.succeeded(key)
    try:
        accounts.set_password(viewer.id, payload.new)
    except AccountError as exc:
        raise _unprocessable(exc) from None
    accounts.close_sessions(viewer.id, keep=viewer.session_id)
    db.commit()


def _unprocessable(exc: AccountError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))

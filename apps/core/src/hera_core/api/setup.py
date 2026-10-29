"""Claiming a fresh instance, and what an admin says about it afterwards.

The wizard's first step is the only one this module guards specially: it makes the admin and
signs them in, and from then on the wizard is an admin using ordinary routes — ``/instance``
below, and the Models screen's own probe for the endpoint. So there is one privileged act, and
it is refused the moment anybody can sign in.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from hera_accounts import AccountError, Accounts, EmailTaken, Purpose
from hera_chats import ChatRepository
from hera_core.auth import client_key, is_loopback, sign_in_as
from hera_core.claim import claim_as_admin, normalise_code, unclaimed
from hera_core.config import load as load_config
from hera_core.config import save as save_config
from hera_core.deps import AdminOnly, Container, Db
from hera_core.schemas import AccountOut, InstanceOut, InstancePatch, SetupIn, SetupOut

router = APIRouter(tags=["setup"])
instance_router = APIRouter(tags=["setup"])


@router.get("/setup", response_model=SetupOut)
def setup_state(request: Request, container: Container, db: Db) -> SetupOut:
    required = unclaimed(db)
    chats = len(ChatRepository(db).for_owner(container.settings.owner_id)) if required else 0
    return SetupOut(required=required, code_required=not is_loopback(request), chats=chats)


@router.post("/setup", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def claim(
    payload: SetupIn, request: Request, response: Response, container: Container, db: Db
) -> AccountOut:
    """Make the first admin and sign them in.

    From anywhere but the machine itself this needs the setup code from the server's log, or a
    launch token from the desktop app that started the server (ADR 27).
    """
    if not unclaimed(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="this Hera already has an admin"
        )
    if not is_loopback(request):
        key = f"setup:{client_key(request)}"
        container.throttle.check(key)
        accounts = Accounts(db)
        launched = bool(payload.launch_token) and (
            accounts.redeem(Purpose.LAUNCH, payload.launch_token) is not None
        )
        if not launched and accounts.redeem(Purpose.SETUP, normalise_code(payload.code)) is None:
            container.throttle.failed(key)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="that setup code is not right — it is in the server's log, and in "
                "~/.hera/setup-code on the machine Hera runs on",
            )
        container.throttle.succeeded(key)
    try:
        user = claim_as_admin(
            db,
            container.settings.owner_id,
            email=payload.email,
            name=payload.name,
            password=payload.password,
        )
    except EmailTaken as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except AccountError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None
    sign_in_as(db, request, response, user)
    return AccountOut.of(user)


@instance_router.get("/instance", response_model=InstanceOut)
def read_instance() -> InstanceOut:
    return InstanceOut.of(load_config().instance)


@instance_router.patch("/instance", response_model=InstanceOut, dependencies=[AdminOnly])
def write_instance(payload: InstancePatch) -> InstanceOut:
    changes = payload.model_dump(exclude_none=True)
    try:
        config = load_config().with_instance(**changes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None
    save_config(config)
    return InstanceOut.of(config.instance)

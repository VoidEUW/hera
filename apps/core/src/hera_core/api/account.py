"""The owner's account: a name, an email and an avatar.

Three routes for the record and three for the picture. No login hides behind any of them —
``Owner`` is the same single id every other route resolves — which is why password, two-factor
and passkeys are not here: they are drawn on the screen as *coming later* and built when there
is something to log in to.
"""

from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, HTTPException, Response, status

from hera_core.account import AVATAR_TYPES, MAX_AVATAR_BYTES, account_for, sniffs_as
from hera_core.deps import Db, Owner
from hera_core.schemas import AccountOut, AccountPatch, AvatarIn
from hera_home import avatar_path

router = APIRouter(tags=["account"])


@router.get("/account", response_model=AccountOut)
def read_account(owner: Owner, db: Db) -> AccountOut:
    return AccountOut.of(account_for(db, owner))


@router.patch("/account", response_model=AccountOut)
def write_account(payload: AccountPatch, owner: Owner, db: Db) -> AccountOut:
    account = account_for(db, owner)
    if payload.name is not None:
        account.name = payload.name
    if payload.email is not None:
        account.email = payload.email
    db.add(account)
    db.commit()
    return AccountOut.of(account)


@router.put("/account/avatar", response_model=AccountOut)
def put_avatar(payload: AvatarIn, owner: Owner, db: Db) -> AccountOut:
    """Replace the picture. Held to the limits an image attachment is: the four types the model
    can be shown, 12 MB, and bytes that really are what the header says."""
    media_type, data = _decode(payload.data_url)
    account = account_for(db, owner)
    path = avatar_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    account.avatar_type = media_type
    db.add(account)
    db.commit()
    return AccountOut.of(account)


@router.delete("/account/avatar", response_model=AccountOut)
def delete_avatar(owner: Owner, db: Db) -> AccountOut:
    account = account_for(db, owner)
    avatar_path().unlink(missing_ok=True)
    account.avatar_type = ""
    db.add(account)
    db.commit()
    return AccountOut.of(account)


@router.get("/account/avatar")
def get_avatar(owner: Owner, db: Db) -> Response:
    account = account_for(db, owner)
    path = avatar_path()
    if not account.avatar_type or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no avatar")
    return Response(
        content=path.read_bytes(),
        media_type=account.avatar_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"},
    )


def _decode(data_url: str) -> tuple[str, bytes]:
    """``data:<type>;base64,<payload>`` into its two halves, or a 422 saying which part is wrong."""
    header, _, body = data_url.partition(",")
    media_type = header.removeprefix("data:").removesuffix(";base64")
    if not header.startswith("data:") or not header.endswith(";base64") or not body:
        raise _refuse("an avatar has to be a base64 data URL")
    if media_type not in AVATAR_TYPES:
        raise _refuse("an avatar has to be a PNG, JPEG, WebP or GIF picture")
    try:
        data = base64.b64decode(body, validate=True)
    except binascii.Error:
        raise _refuse("that picture could not be decoded") from None
    if len(data) > MAX_AVATAR_BYTES:
        raise _refuse("that picture is larger than 12 MB")
    if not sniffs_as(media_type, data):
        raise _refuse("that file is not the kind of picture it says it is")
    return media_type, data


def _refuse(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

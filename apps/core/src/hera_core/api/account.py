"""The signed-in person's account: a name, an email and an avatar.

Three routes for the record and three for the picture. Signing in, sessions and the password
are ``api.auth``; this is what a person says about themselves once they are in.
"""

from __future__ import annotations

import base64
import binascii
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import Session

from hera_accounts import Accounts, EmailTaken, User
from hera_core.account import AVATAR_TYPES, MAX_AVATAR_BYTES, sniffs_as
from hera_core.deps import Db, Owner
from hera_core.schemas import AccountOut, AccountPatch, AvatarIn
from hera_home import avatar_path
from hera_storage import utcnow

router = APIRouter(tags=["account"])


@router.get("/account", response_model=AccountOut)
def read_account(owner: Owner, db: Db) -> AccountOut:
    return AccountOut.of(_user(db, owner))


@router.patch("/account", response_model=AccountOut)
def write_account(payload: AccountPatch, owner: Owner, db: Db) -> AccountOut:
    try:
        user = Accounts(db).update(_user(db, owner), name=payload.name, email=payload.email)
    except EmailTaken as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    db.commit()
    return AccountOut.of(user)


@router.put("/account/avatar", response_model=AccountOut)
def put_avatar(payload: AvatarIn, owner: Owner, db: Db) -> AccountOut:
    """Replace the picture. Held to the limits an image attachment is: the four types the model
    can be shown, 12 MB, and bytes that really are what the header says."""
    media_type, data = _decode(payload.data_url)
    user = _user(db, owner)
    path = avatar_path(str(owner))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _set_avatar_type(db, user, media_type)


@router.delete("/account/avatar", response_model=AccountOut)
def delete_avatar(owner: Owner, db: Db) -> AccountOut:
    user = _user(db, owner)
    avatar_path(str(owner)).unlink(missing_ok=True)
    return _set_avatar_type(db, user, "")


@router.get("/account/avatar")
def get_avatar(owner: Owner, db: Db) -> Response:
    user = _user(db, owner)
    path = avatar_path(str(owner))
    if not user.avatar_type or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no avatar")
    return Response(
        content=path.read_bytes(),
        media_type=user.avatar_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"},
    )


def _user(db: Session, owner: UUID) -> User:
    user = Accounts(db).get(owner)
    if user is None:
        # Signed in a moment ago and gone now: an admin removed the account in between.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="sign in first")
    return user


def _set_avatar_type(db: Session, user: User, media_type: str) -> AccountOut:
    user.avatar_type = media_type
    user.updated_at = utcnow()
    db.add(user)
    db.commit()
    return AccountOut.of(user)


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

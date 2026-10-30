"""Settings → Admin → Users, and inviting somebody (ADR 27).

Two doors. ``/users`` is the admin's: the list, roles, disabling, a fresh link, signing somebody
out, deleting them. ``/invitations`` is narrower and wider at once — an admin may invite anybody
as anything, and while registration is ``invite`` any signed-in person may invite somebody as a
user, which is the one thing that setting means.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from hera_accounts import AccountError, Accounts, EmailTaken, LastAdmin, Role, User
from hera_core import links
from hera_core import users as people_admin
from hera_core.config import load as load_config
from hera_core.deps import Admin, AdminOnly, Container, Db, SignedIn, not_found
from hera_core.schemas import InvitationIn, InvitationOut, SentOut, UserOut, UserPatch

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[UserOut], dependencies=[AdminOnly])
def list_users(db: Db) -> list[UserOut]:
    accounts = Accounts(db)
    seen = accounts.last_seen()
    return [_out(accounts, user, seen) for user in accounts.users()]


@router.post("/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
def invite(
    payload: InvitationIn, viewer: SignedIn, request: Request, container: Container, db: Db
) -> InvitationOut:
    """Make an account with no password and send its owner a link to choose one."""
    config = load_config()
    if not viewer.is_admin:
        if config.instance.registration != "invite":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="only an admin can invite people here"
            )
        if payload.role != "user":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="only an admin can make an admin"
            )
    accounts = Accounts(db)
    try:
        user = accounts.create(payload.email, name=payload.name, role=Role(payload.role))
    except EmailTaken as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except AccountError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None
    inviter = accounts.get(viewer.id)
    sent = links.send(
        accounts,
        container.mailer,
        config,
        user,
        base=links.base_for(request, config, bind_host=container.settings.host),
        commit=db.commit,
        inviter=(inviter.name or inviter.email) if inviter is not None else "",
    )
    return InvitationOut(
        link=sent.link,
        mailed=sent.mailed,
        mail_error=sent.mail_error,
        user=_out(accounts, user, {}),
    )


@router.patch("/users/{user_id}", response_model=UserOut)
def change_user(user_id: UUID, payload: UserPatch, admin: Admin, db: Db) -> UserOut:
    accounts = Accounts(db)
    user = _require(accounts, user_id)
    if payload.disabled and user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="you cannot disable your own account"
        )
    try:
        if payload.role is not None:
            accounts.set_role(user, Role(payload.role))
        if payload.disabled is not None:
            accounts.set_disabled(user, payload.disabled)
    except LastAdmin as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return _out(accounts, user, accounts.last_seen())


@router.post("/users/{user_id}/link", response_model=SentOut)
def send_link(
    user_id: UUID,
    admin: Admin,
    request: Request,
    container: Container,
    db: Db,
    mail: bool = True,
) -> SentOut:
    """A new invitation for somebody who has not chosen a password yet, or a reset link for
    somebody who has — mailed when mail is set up and ``mail`` is not ``false``, and handed back
    to copy either way. Either way it replaces the link sent before."""
    accounts = Accounts(db)
    user = _require(accounts, user_id)
    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="enable this account before sending a link"
        )
    config = load_config()
    inviter = accounts.get(admin.id)
    sent = links.send(
        accounts,
        container.mailer,
        config,
        user,
        base=links.base_for(request, config, bind_host=container.settings.host),
        commit=db.commit,
        inviter=(inviter.name or inviter.email) if inviter is not None else "",
        by_mail=mail,
    )
    return SentOut(link=sent.link, mailed=sent.mailed, mail_error=sent.mail_error)


@router.delete(
    "/users/{user_id}/sessions", status_code=status.HTTP_204_NO_CONTENT, dependencies=[AdminOnly]
)
def sign_out_user(user_id: UUID, db: Db) -> None:
    accounts = Accounts(db)
    accounts.close_sessions(_require(accounts, user_id).id)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, admin: Admin, container: Container, db: Db) -> None:
    """The account and everything of theirs: chats, projects, memories, their mind. Disabling
    is the way to keep it all."""
    accounts = Accounts(db)
    user = _require(accounts, user_id)
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="you cannot delete your own account"
        )
    try:
        chats = people_admin.remove(db, user)
    except LastAdmin as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    db.commit()
    container.people.forget(user_id)
    people_admin.remove_files(user_id, chats)


def _require(accounts: Accounts, user_id: UUID) -> User:
    user = accounts.get(user_id)
    if user is None:
        raise not_found("user")
    return user


def _out(accounts: Accounts, user: User, seen: dict[UUID, datetime]) -> UserOut:
    return UserOut.of(user, invited=not accounts.has_password(user.id), last_seen=seen.get(user.id))

"""FastAPI dependencies: who is asking, and what they may reach.

``current_user`` is the multi-user seam. Every route resolves an owner through it and every row
carries ``owner_id``, so when sign-in arrived (ADR 27) it changed what *this function* reads — a
session cookie instead of a constant — and not what it returns. A route that reads the owner
from anywhere else is the bug that seam exists to prevent.

``Admin`` is the second dependency beside it: what an instance route asks for, which answers
403 to somebody who is signed in and is not one.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session

from hera_accounts import Accounts
from hera_chats import Chat, ChatRepository
from hera_core.auth import Viewer, session_token
from hera_core.wiring import Services
from hera_storage import Database


def services(request: Request) -> Services:
    """Everything built at startup, off the application state."""
    return request.app.state.services  # type: ignore[no-any-return]  # set in the lifespan


def viewer(request: Request, container: Annotated[Services, Depends(services)]) -> Viewer:
    """Who is signed in, from the session cookie, or a 401.

    Its own short unit of work rather than the request's: using a session pushes its expiry back,
    and that write should not wait on — or be rolled back with — whatever the route then does.
    """
    with container.database.session() as db:
        found = Accounts(db).resolve(session_token(request))
        if found is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="sign in first")
        user, sign_in = found
        return Viewer(id=user.id, role=user.role, session_id=sign_in.id)


def current_user(signed_in: Annotated[Viewer, Depends(viewer)]) -> UUID:
    """Whose data this request may touch."""
    return signed_in.id


def require_admin(signed_in: Annotated[Viewer, Depends(viewer)]) -> Viewer:
    """An admin, or a 403. Instance routes — endpoints, servers, skills, policy — ask for this."""
    if not signed_in.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="only an admin can change that"
        )
    return signed_in


def database(container: Annotated[Services, Depends(services)]) -> Database:
    return container.database


def session(container: Annotated[Services, Depends(services)]) -> Iterator[Session]:
    """One unit of work per request. Commits on success, rolls back on any exception."""
    with container.database.session() as active:
        yield active


Container = Annotated[Services, Depends(services)]
Owner = Annotated[UUID, Depends(current_user)]
SignedIn = Annotated[Viewer, Depends(viewer)]
Admin = Annotated[Viewer, Depends(require_admin)]
AdminOnly = Depends(require_admin)
"""For a route's ``dependencies=[...]``, where the admin's identity is not otherwise used."""
Db = Annotated[Session, Depends(session)]


def not_found(what: str) -> HTTPException:
    """A 404 that does not distinguish "does not exist" from "is not yours".

    Telling someone that a chat exists but belongs to another account is more than a 404 should
    ever teach. One message for both, from one place, so no route can be the exception.
    """
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no such {what}")


def require_chat(session: Session, chat_id: UUID, owner: UUID) -> Chat:
    """A chat this owner has, or a 404 that says nothing about which of the two it was.

    Here rather than in a route module because two of them need it now — the transcript and the
    artifacts beside it — and a route importing another route for one function is how a request
    layer grows a private API. ``api.projects`` and ``api.chats`` still keep their own
    ``_require_project`` for that reason; what moved is the one with a second caller.
    """
    chat = ChatRepository(session).get(chat_id)
    if chat is None or chat.owner_id != owner:
        raise not_found("chat")
    return chat

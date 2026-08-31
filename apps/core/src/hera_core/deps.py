"""FastAPI dependencies: who is asking, and what they may reach.

``current_user`` is the multi-user seam. v0.1 has one person and no login, but every route
resolves an owner through this function and every row carries ``owner_id`` — so adding a login
screen later is a change to *this function* rather than to every query. A route that reads the
owner from anywhere else is the bug that seam exists to prevent, which is why the id is not
simply importable as a constant.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session

from hera_chats import Chat, ChatRepository
from hera_core.wiring import Services
from hera_storage import Database


def services(request: Request) -> Services:
    """Everything built at startup, off the application state."""
    return request.app.state.services  # type: ignore[no-any-return]  # set in the lifespan


def current_user(container: Annotated[Services, Depends(services)]) -> UUID:
    """Whose data this request may touch."""
    return container.settings.owner_id


def database(container: Annotated[Services, Depends(services)]) -> Database:
    return container.database


def session(container: Annotated[Services, Depends(services)]) -> Iterator[Session]:
    """One unit of work per request. Commits on success, rolls back on any exception."""
    with container.database.session() as active:
        yield active


Container = Annotated[Services, Depends(services)]
Owner = Annotated[UUID, Depends(current_user)]
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

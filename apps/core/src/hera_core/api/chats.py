"""Chats, messages, and the streaming turn.

The turn endpoint is the one piece of real work in this package. Everything else is a list.

**Sessions are opened deliberately, not by a dependency.** A `Depends`-provided session stays
open for as long as the response does, and a streaming response lasts as long as the model
takes — which would hold a SQLite write transaction open across a minute of generation and
block every other request behind it. So the route does its preparation in one short unit of
work, commits, and the generator opens a second one at the end to record. Between the two,
nothing holds the database.

**Cancellation is a supported outcome.** When the browser goes away, Starlette closes the
generator; `hera_chats` closes the turn as `cancelled` with the text that did arrive, and the
`finally` block still persists it. Navigating away mid-answer keeps the half you read.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
from hera_chats.events import ChatEvent, PermissionDecided, PermissionRequired
from sqlmodel import Session

from hera_chats import (
    Attachment,
    Chat,
    ChatRepository,
    Message,
    MessageRepository,
    ProjectRepository,
    Turn,
    TurnContext,
    build_history,
    events_of,
    title_from,
)
from hera_core.deps import Container, Db, Owner, not_found
from hera_core.schemas import ChatDetail, ChatIn, ChatOut, MessageIn, MessageOut, PermissionAnswer
from hera_core.sse import HEADERS, MEDIA_TYPE, event_frame, frame
from hera_permissions import Decision, Rule
from hera_profiles import Profile, ProfileRepository
from hera_providers import ToolCallReady
from hera_skillsets import SkillUsageRepository

router = APIRouter(tags=["chats"])


@router.get("/chats", response_model=list[ChatOut])
def list_chats(owner: Owner, db: Db, project_id: UUID | None = None) -> list[ChatOut]:
    """The sidebar's list, most recently active first."""
    chats = ChatRepository(db)
    found = (
        chats.for_owner(owner, project_id=project_id)
        if project_id is not None
        else chats.for_owner(owner)
    )
    return [ChatOut.of(chat) for chat in found]


@router.post("/chats", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
def create_chat(payload: ChatIn, owner: Owner, db: Db) -> ChatOut:
    """Open a chat.

    A chat with no profile falls back to the owner's default at the moment it is created, not
    at the moment it is answered — so changing the default later does not retroactively change
    who answered an old conversation.
    """
    profile_id = payload.profile_id
    if profile_id is None:
        default = ProfileRepository(db).default_for(owner)
        profile_id = default.id if default is not None else None
    chat = ChatRepository(db).create(
        owner,
        title=payload.title,
        project_id=payload.project_id,
        profile_id=profile_id,
    )
    return ChatOut.of(chat)


@router.get("/chats/{chat_id}", response_model=ChatDetail)
def read_chat(chat_id: UUID, owner: Owner, db: Db) -> ChatDetail:
    """A chat and every message in it — what a reload renders from."""
    chat = _require_chat(db, chat_id, owner)
    return ChatDetail(
        chat=ChatOut.of(chat),
        messages=[MessageOut.of(m) for m in MessageRepository(db).for_chat(chat.id)],
    )


@router.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: UUID, owner: Owner, db: Db) -> None:
    chat = _require_chat(db, chat_id, owner)
    MessageRepository(db).delete_for_chat(chat.id)
    ChatRepository(db).revoke(chat.id)


@router.post("/chats/{chat_id}/messages")
def send_message(
    chat_id: UUID, payload: MessageIn, owner: Owner, db: Db, container: Container
) -> StreamingResponse:
    """Say something, and stream the answer.

    The user message and an empty assistant message are written *before* the model is asked.
    The empty row is what a resumed turn appends to and what a cancelled turn lands in; a row
    created only on success would leave a half-written answer with nowhere to live.
    """
    chat = _require_chat(db, chat_id, owner)
    messages = MessageRepository(db)

    attachments = [Attachment(**item.model_dump()) for item in payload.attachments]
    messages.add_user_message(chat, payload.text, attachments)
    ChatRepository(db).touch(chat)
    assistant = messages.start_assistant_message(chat)

    return _stream(container, db, chat, assistant, text=payload.text, attachments=attachments)


@router.post("/chats/{chat_id}/permissions")
def answer_permission(
    chat_id: UUID, payload: PermissionAnswer, owner: Owner, db: Db, container: Container
) -> StreamingResponse:
    """Answer a permission card and resume the turn it stopped.

    Resumes the *same* assistant message rather than starting a new one, so the conversation
    reads as one answer that paused rather than as two.
    """
    chat = _require_chat(db, chat_id, owner)
    assistant = MessageRepository(db).latest_assistant(chat.id)
    if assistant is None:
        raise not_found("turn to resume")

    recorded = events_of(assistant)
    answered = set(payload.call_ids)
    decisions = [
        PermissionDecided(call_id=call_id, allowed=payload.allow, remembered=payload.remember)
        for call_id in payload.call_ids
    ]

    if payload.remember and container.registry is not None:
        _remember(container, recorded, answered, allow=payload.allow)

    return _stream(
        container,
        db,
        chat,
        assistant,
        text="",
        lead=decisions,
        resume=[*recorded, *decisions],
        confirmed=payload.call_ids if payload.allow else [],
        denied=[] if payload.allow else payload.call_ids,
    )


# -- the streaming half ------------------------------------------------------------------


def _stream(
    container: Container,
    db: Session,
    chat: Chat,
    assistant: Message,
    *,
    text: str,
    lead: Sequence[ChatEvent] = (),
    **extra: object,
) -> StreamingResponse:
    """Close this request's unit of work, then stream the turn.

    **The commit here is load-bearing.** A ``Depends``-provided session commits when the
    dependency is torn down, which for a streaming response is *after the last byte* — so
    without this, the recording session opened further down would look for an assistant row
    that is still sitting uncommitted in another transaction, find nothing, and persist the
    whole turn into the void. The answer would stream perfectly and be gone on reload.

    **The expunge is load-bearing too.** ``commit()`` expires every instance, and the turn
    reads the profile and the project from a worker thread. Detaching them while their columns
    are loaded makes them plain readable objects; leaving them attached would have SQLAlchemy
    refresh them from a session it does not own, off the thread that opened it.

    ``lead`` is the permission decisions. They travel in ``resume`` so the turn records and
    persists them, and a resumed turn deliberately does not re-stream what it inherited — the
    client is already rendering that half. These are the exception: they were made by *this*
    request, so without them the card only settles on the ``done`` re-render.
    """
    db.commit()

    context = _context(db, chat, text=text, **extra)
    owner_id, chat_id, message_id = chat.owner_id, chat.id, assistant.id
    db.expunge_all()

    turn = container.orchestrator.begin(context)

    async def frames() -> AsyncIterator[str]:
        try:
            for event in lead:
                yield event_frame(event)
            async for event in turn.stream():
                yield event_frame(event)
        finally:
            # Runs on a normal finish, on a client that hung up, and on a failure. Whatever
            # the turn recorded is persisted either way -- that is the point of `recorded`
            # being correct at every moment rather than only at the end.
            persisted = _record(container, owner_id, chat_id, message_id, turn)
            if persisted is not None:
                yield frame("done", persisted)

    return StreamingResponse(frames(), media_type=MEDIA_TYPE, headers=dict(HEADERS))


def _record(
    container: Container, owner_id: UUID, chat_id: UUID, message_id: UUID, turn: Turn
) -> dict[str, Any] | None:
    """Store the turn in its own short unit of work, and return the ``done`` payload.

    Its own, because the request's unit of work was committed and detached before streaming
    started. Serialised **inside** the block for the same reason the ids are captured outside
    it: the instance is expired the moment the session closes, so a `MessageOut.of` after the
    fact would try to refresh a detached row.

    The payload is what the client replaces its optimistic view with, which is what makes the
    server render authoritative rather than merely agreed with.
    """
    with container.database.session() as session:
        messages = MessageRepository(session)
        message = messages.get(message_id)
        if message is None:
            return None
        messages.record(message, turn.recorded, prompt_fingerprint=turn.prompt_fingerprint)
        if turn.skill_ids:
            SkillUsageRepository(session).record(owner_id, turn.skill_ids)
        chat = ChatRepository(session).get(chat_id)
        if chat is not None:
            # Titled from the text the router *kept*. `/tdd` is addressed to the application
            # rather than to her, and a sidebar full of commands is a sidebar you cannot skim.
            ChatRepository(session).touch(chat, title=title_from(turn.cleaned_text))
        return MessageOut.of(message).model_dump(mode="json")


# -- assembling one turn ------------------------------------------------------------------


def _context(session: Session, chat: Chat, *, text: str, **extra: object) -> TurnContext:
    """Gather the profile, the project and the history for one turn."""
    profile = _profile_of(session, chat)
    project = None
    if chat.project_id is not None:
        project = ProjectRepository(session).get(chat.project_id)
    history = build_history(MessageRepository(session).for_chat(chat.id))
    return TurnContext(
        text=text,
        chat=chat,
        project=project,
        profile=profile,
        history=history,
        **extra,  # type: ignore[arg-type]  # resume/confirmed/denied, forwarded to the dataclass
    )


def _profile_of(session: Session, chat: Chat) -> Profile | None:
    profiles = ProfileRepository(session)
    if chat.profile_id is not None:
        found = profiles.get(chat.profile_id)
        if found is not None:
            return found
    # A chat whose profile was revoked still has to answer. Falling back to the default beats
    # both refusing and answering as nobody in particular.
    return profiles.default_for(chat.owner_id)


def _remember(
    container: Container, recorded: Sequence[ChatEvent], answered: set[str], *, allow: bool
) -> None:
    """Turn "always allow" into a rule.

    Written against the **exact tool name**, not a pattern derived from it. A card about
    ``fs__write_file`` answered with "always" must not quietly permit ``fs__delete_file``; if
    somebody wants the broader rule they can widen it on the Permissions screen, where they can
    see what they are doing.
    """
    if container.registry is None:
        return
    tools = {
        event.name
        for event in recorded
        if isinstance(event, ToolCallReady) and event.id in answered
    } or {
        event.tool
        for event in recorded
        if isinstance(event, PermissionRequired) and event.call_id in answered
    }
    policy = container.registry.policy
    for tool in sorted(tools):
        policy = policy.with_rule(
            Rule(
                pattern=tool,
                decision=Decision.ALLOW if allow else Decision.DENY,
                reason="answered on a confirmation card",
            )
        )
    container.registry = container.registry.with_policy(policy)
    container.orchestrator.registry = container.registry


def _require_chat(session: Session, chat_id: UUID, owner: UUID) -> Chat:
    chat = ChatRepository(session).get(chat_id)
    if chat is None or chat.owner_id != owner:
        raise not_found("chat")
    return chat

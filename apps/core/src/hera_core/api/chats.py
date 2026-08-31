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

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from hera_chats.events import (
    AnswerGiven,
    AnswerRequired,
    ChatEvent,
    PermissionDecided,
    PermissionRequired,
)
from sqlmodel import Session

from hera_chats import (
    Attachment,
    Chat,
    ChatRepository,
    Message,
    MessageRepository,
    Project,
    ProjectRepository,
    Turn,
    TurnContext,
    build_history,
    events_of,
    title_from,
)
from hera_core.chat_files import forget_chat
from hera_core.clock import render as render_now
from hera_core.config import ConfigError
from hera_core.config import load as load_config
from hera_core.deps import Container, Db, Owner, not_found, require_chat
from hera_core.emotions import EmotionsError
from hera_core.emotions import load as load_emotions
from hera_core.schemas import (
    ChatDetail,
    ChatIn,
    ChatOut,
    ChatPatch,
    MessageIn,
    MessageOut,
    PermissionAnswer,
    QuestionAnswer,
    RedoIn,
)
from hera_core.sse import HEADERS, MEDIA_TYPE, event_frame, frame
from hera_mcp import DEFAULT_EMOTIONS, render_emotions
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
    chat = require_chat(db, chat_id, owner)
    return ChatDetail(
        chat=ChatOut.of(chat),
        messages=[MessageOut.of(m) for m in MessageRepository(db).for_chat(chat.id)],
    )


@router.patch("/chats/{chat_id}", response_model=ChatOut)
def update_chat(chat_id: UUID, payload: ChatPatch, owner: Owner, db: Db) -> ChatOut:
    """Rename a chat, move it between projects, or change which skills are switched on inside it.

    Whitespace is stripped from a title, and a title of nothing is allowed: it hands the name
    back to her, since a chat with no title is the one case a finished turn will name.

    Pinning here is ADR 5 in the person's hands. Retrieval decides what *might* apply; a pin
    says *use this*, and the turn puts the chat's pins ahead of the profile's and the
    project's — the most specific and the most deliberate of the three.

    Moving is the one field where ``None`` is a value rather than an omission — see
    :class:`~hera_core.schemas.ChatPatch`. It changes which project's instructions and pins the
    *next* turn carries and nothing about the turns already taken, which is the honest
    behaviour: a conversation is a record of what was said under the conditions of the time.
    """
    chat = require_chat(db, chat_id, owner)
    chats = ChatRepository(db)
    if payload.title is not None:
        chat.title = payload.title.strip()
    if payload.pinned_skills is not None:
        # Not validated against what is installed: a pin whose folder is gone is reported by
        # the router as `missing`, which is the useful outcome — refusing it here would mean a
        # skill temporarily moved aside silently loses every pin that named it.
        chats.set_pinned_skills(chat, payload.pinned_skills)
    if "project_id" in payload.model_fields_set:
        # Checked, unlike a skill pin: a project is a row this owner either has or does not,
        # and a chat pointing at somebody else's project would show its instructions to the
        # wrong person. `project_id` is a bare UUID with no foreign key to catch that.
        if payload.project_id is not None:
            _require_project(db, payload.project_id, owner)
        chat.project_id = payload.project_id
    return ChatOut.of(chats.save(chat))


@router.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: UUID, owner: Owner, db: Db) -> None:
    chat = require_chat(db, chat_id, owner)
    MessageRepository(db).delete_for_chat(chat.id)
    ChatRepository(db).revoke(chat.id)
    # ADR 12 is explicit that the scratchpad is a cache rather than something a person keeps, so
    # cleaning it up is part of deleting the chat rather than a chore for later. It never
    # raises: a row that is gone and a directory that would not go is a stale directory, and
    # failing the delete button over it would leave the row behind as well.
    forget_chat(str(chat.id))


@router.post("/chats/{chat_id}/messages")
def send_message(
    chat_id: UUID, payload: MessageIn, owner: Owner, db: Db, container: Container
) -> StreamingResponse:
    """Say something, and stream the answer.

    The user message and an empty assistant message are written *before* the model is asked.
    The empty row is what a resumed turn appends to and what a cancelled turn lands in; a row
    created only on success would leave a half-written answer with nowhere to live.
    """
    chat = require_chat(db, chat_id, owner)
    messages = MessageRepository(db)

    attachments = [Attachment(**item.model_dump()) for item in payload.attachments]
    messages.add_user_message(chat, payload.text, attachments)
    ChatRepository(db).touch(chat)
    assistant = messages.start_assistant_message(chat)

    return _stream(container, db, chat, assistant, text=payload.text, attachments=attachments)


@router.post("/chats/{chat_id}/messages/{message_id}/redo")
def redo_message(
    chat_id: UUID,
    message_id: UUID,
    payload: RedoIn,
    owner: Owner,
    db: Db,
    container: Container,
) -> StreamingResponse:
    """Ask again from here — the same question, or a reworded one.

    One route for what the interface calls two things, because they are one thing: **edit**
    sends new text for a question, **try again** sends none for an answer. Both mean "the
    conversation goes forward from this point differently", and both need the same rewind.

    Point it at an *assistant* message and the question above it is the one replayed. That is
    the only sensible reading — a turn is an answer to something, and re-running it without its
    question would be re-running nothing.

    Everything from that question onwards is deleted first, deliberately: an answer to the old
    wording is not an answer to the new one, and the model reads history from the message list.
    Which is also why this streams like any other turn — from here on it *is* one.
    """
    chat = require_chat(db, chat_id, owner)
    messages = MessageRepository(db)
    history = messages.for_chat(chat.id)

    target = next((message for message in history if message.id == message_id), None)
    if target is None:
        raise not_found("message")

    asked = _question_behind(history, target)
    if asked is None:
        raise not_found("question to ask again")

    text = asked.content if payload.text is None else payload.text
    attachments = [Attachment(**item) for item in asked.attachments]
    if not text.strip() and not attachments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="a message needs text, a file, or both",
        )

    messages.truncate_from(chat.id, asked.sequence)
    messages.add_user_message(chat, text, attachments)
    ChatRepository(db).touch(chat)
    assistant = messages.start_assistant_message(chat)

    return _stream(container, db, chat, assistant, text=text, attachments=attachments)


def _question_behind(history: Sequence[Message], target: Message) -> Message | None:
    """The user message a redo replays: this one, or the one this answer was answering."""
    if target.role == "user":
        return target
    earlier = [
        message
        for message in history
        if message.role == "user" and message.sequence < target.sequence
    ]
    return earlier[-1] if earlier else None


@router.post("/chats/{chat_id}/permissions")
def answer_permission(
    chat_id: UUID, payload: PermissionAnswer, owner: Owner, db: Db, container: Container
) -> StreamingResponse:
    """Answer a permission card and resume the turn it stopped.

    Resumes the *same* assistant message rather than starting a new one, so the conversation
    reads as one answer that paused rather than as two.
    """
    chat = require_chat(db, chat_id, owner)
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


@router.post("/chats/{chat_id}/answers")
def answer_question(
    chat_id: UUID, payload: QuestionAnswer, owner: Owner, db: Db, container: Container
) -> StreamingResponse:
    """Reply to a question she asked, and resume the turn it stopped.

    The same route the permission card has, doing the same thing to the same machinery — which
    is the point of `docs/tooling.md` § 4's argument for generalising the suspension rather than
    building a second one. The only difference is what settles the call: a decision there, a
    sentence here, and the sentence becomes the call's result so the model reads a reply to its
    own question where a tool's output would have been.
    """
    chat = require_chat(db, chat_id, owner)
    assistant = MessageRepository(db).latest_assistant(chat.id)
    if assistant is None:
        raise not_found("turn to resume")

    recorded = events_of(assistant)
    # Checked against the paused turn rather than trusted: a call id that was never asked about
    # would otherwise resume a turn with an answer to nothing in it, and the model would be
    # handed a tool result for a call it never made.
    asked = {event.call_id for event in recorded if isinstance(event, AnswerRequired)}
    if payload.call_id not in asked:
        raise not_found("question to answer")

    given = AnswerGiven(call_id=payload.call_id, text=payload.text)

    return _stream(
        container,
        db,
        chat,
        assistant,
        text="",
        lead=[given],
        resume=[*recorded, given],
        answers={payload.call_id: payload.text},
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

    context = _context(
        db,
        chat,
        text=text,
        history_limit=container.orchestrator.settings.max_history_argument_chars,
        **extra,
    )
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


def _context(
    session: Session, chat: Chat, *, text: str, history_limit: int, **extra: object
) -> TurnContext:
    """Gather the profile, the project, the history and the vocabulary for one turn.

    ``history_limit`` is passed rather than left to the default so the setting is a setting: a
    value a deployment can change that quietly does not apply is worse than one that is not
    offered. It shortens a string argument that is really a document — a page published in turn
    four is otherwise in the prompt of every turn after it.
    """
    profile = _profile_of(session, chat)
    project = None
    if chat.project_id is not None:
        project = ProjectRepository(session).get(chat.project_id)
    history = build_history(
        MessageRepository(session).for_chat(chat.id), max_argument_chars=history_limit
    )
    return TurnContext(
        text=text,
        chat=chat,
        project=project,
        profile=profile,
        history=history,
        emotions=_emotion_vocabulary(),
        now=_now(),
        **extra,  # type: ignore[arg-type]  # resume/confirmed/denied, forwarded to the dataclass
    )


def _now() -> str:
    """The date and time, for the ``now`` slot.

    Read per turn and per request, like the emotion vocabulary above and for the same reason: a
    timezone changed on screen has to apply to the next turn rather than the next restart. It is
    also the only honest place to compute *now* — a value captured at boot would be a day stale
    by the second day the process was up.

    A `config.toml` that will not parse falls back to UTC rather than propagating: the Models
    screen is where a broken file gets explained, and losing the date over it would trade a
    visible problem for a silent one.
    """
    try:
        timezone = load_config().timezone
    except ConfigError:
        timezone = ""
    return render_now(timezone)


def _emotion_vocabulary() -> str:
    """Her stances, rendered for the prompt.

    Read per turn rather than at startup: the Emotions screen writes a file, and a vocabulary
    you can edit on screen that only applies after a restart is the trap `config.toml` already
    taught this project once. A file that will not parse falls back to the shipped list — the
    Emotions screen is where that gets explained, and a turn is not the place to find out.
    """
    try:
        return render_emotions(load_emotions())
    except EmotionsError:
        return render_emotions(list(DEFAULT_EMOTIONS))


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


def _require_project(session: Session, project_id: UUID, owner: UUID) -> Project:
    """A project this owner has, or a 404.

    Deliberately the same answer for *no such project* and *somebody else's project*: the second
    is the first as far as this owner is concerned, and a 403 would confirm the row exists.
    ``hera_core.api.projects`` has the same helper for the same reason; they are not shared
    because a route module importing another route module for one function is how a request
    layer grows a private API. The *chat* one had a second caller when the artifacts beside a
    conversation got their own router, and moved to ``hera_core.deps`` rather than being copied a
    third time — which is the line: duplication between two routes is a convention, between three
    it is a bug waiting for one of them to drift.
    """
    project = ProjectRepository(session).get(project_id)
    if project is None or project.owner_id != owner:
        raise not_found("project")
    return project

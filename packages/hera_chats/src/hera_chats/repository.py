"""Data access for projects, chats and messages.

Nothing commits — that happens in :meth:`hera_storage.Database.session`, so a message, its
chat's ``last_message_at`` and a skill's usage count all land together or not at all.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, col, desc, func

from hera_chats.events import CHAT_EVENT_ADAPTER, ChatEvent, visible_text
from hera_chats.history import Attachment
from hera_chats.models import JSON_FIELDS, Chat, Message, Project
from hera_storage import Repository, utcnow

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """A URL-safe handle. Never empty."""
    slug = _SLUG_STRIP.sub("-", name.strip().lower()).strip("-")
    return slug or "project"


def title_from(text: str, *, limit: int = 60) -> str:
    """A chat title from its first message.

    Only the opening paragraph. A message with a file under it, or a long one with a preamble
    and then the question, would otherwise put its whole body in the sidebar — and a sidebar
    you cannot skim is a sidebar that does not do its job.

    Cut on a word boundary where there is one within reach of the limit, because a title that
    ends mid-word looks like a bug rather than like a truncation.
    """
    opening = text.strip().split("\n\n", 1)[0]
    flat = " ".join(opening.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    spaced = cut.rsplit(" ", 1)[0]
    return f"{spaced if len(spaced) > limit // 2 else cut}…"


def _flag_json(session: Session, obj: object) -> None:
    """Tell SQLAlchemy the JSON columns changed.

    A JSON column holds a list or a dict, and SQLAlchemy detects a change by comparing the
    attribute to its loaded value — the same object after an in-place edit, so no UPDATE is
    issued and the change is lost at the next restart. ``sqlalchemy.ext.mutable`` is the usual
    answer and does not work under SQLModel, whose ``__setattr__`` writes the raw value back
    over SQLAlchemy's coerced one. See ``hera_chats.models.JSON_FIELDS``.
    """
    if obj not in session:
        return
    for name in JSON_FIELDS:
        if hasattr(obj, name):
            flag_modified(obj, name)


class ProjectRepository(Repository[Project]):
    """Projects for one owner."""

    def __init__(self, session: Session) -> None:
        super().__init__(Project, session)

    def for_owner(self, owner_id: UUID, *, include_archived: bool = False) -> list[Project]:
        # `Any`, because a SQLAlchemy filter expression is annotated as the Python type of the
        # comparison it looks like -- `Project.owner_id == owner_id` claims to be a `bool`.
        conditions: list[Any] = [Project.owner_id == owner_id]
        if not include_archived:
            conditions.append(col(Project.archived).is_(False))
        return self.list(*conditions)

    def by_slug(self, owner_id: UUID, slug: str) -> Project | None:
        found = self.list(Project.owner_id == owner_id, Project.slug == slug, limit=1)
        return found[0] if found else None

    def create(self, owner_id: UUID, name: str, **fields: object) -> Project:
        project = Project(
            owner_id=owner_id,
            name=name,
            slug=self._free_slug(owner_id, slugify(name)),
            **fields,
        )
        return self.add(project)

    def save(self, obj: Project) -> Project:
        _flag_json(self.session, obj)
        return super().save(obj)

    def set_pinned_skills(self, project: Project, names: Sequence[str]) -> Project:
        project.pinned_skills = list(names)
        return self.save(project)

    def _free_slug(self, owner_id: UUID, wanted: str) -> str:
        if self.by_slug(owner_id, wanted) is None:
            return wanted
        suffix = 2
        while self.by_slug(owner_id, f"{wanted}-{suffix}") is not None:
            suffix += 1
        return f"{wanted}-{suffix}"


def _by_activity() -> object:
    """Newest activity first, counting creation as activity.

    One expression rather than two ordering terms, because ``last_message_at`` is null until
    something is said and a null sorts to whichever end the backend prefers — so a chat you
    just opened would appear at the bottom of the list you opened it from. Coalescing says
    what is actually meant: when it was last used, or when it was made.
    """
    return desc(func.coalesce(col(Chat.last_message_at), col(Chat.created_at)))


class ChatRepository(Repository[Chat]):
    """Chats for one owner, newest activity first."""

    def __init__(self, session: Session) -> None:
        super().__init__(Chat, session)

    def for_owner(self, owner_id: UUID, *, project_id: UUID | None = None) -> list[Chat]:
        """The sidebar's list, most recently active first."""
        conditions: list[Any] = [Chat.owner_id == owner_id]
        if project_id is not None:
            conditions.append(Chat.project_id == project_id)
        return self.list(*conditions, order_by=_by_activity())

    def loose(self, owner_id: UUID) -> list[Chat]:
        """Chats outside every project — what the start screen opens."""
        return self.list(
            Chat.owner_id == owner_id,
            col(Chat.project_id).is_(None),
            order_by=_by_activity(),
        )

    def create(self, owner_id: UUID, **fields: object) -> Chat:
        return self.add(Chat(owner_id=owner_id, **fields))

    def save(self, obj: Chat) -> Chat:
        # A chat carries a JSON column now (`pinned_skills`), and an in-place edit followed by
        # a bare flush is silently lost. See `_flag_json`.
        _flag_json(self.session, obj)
        return super().save(obj)

    def set_pinned_skills(self, chat: Chat, names: Sequence[str]) -> Chat:
        """Switch skills on for this conversation, by name and in order."""
        chat.pinned_skills = list(dict.fromkeys(names))
        return self.save(chat)

    def touch(self, chat: Chat, *, title: str = "") -> Chat:
        """Record that something was said, and name the chat if it has no name yet."""
        chat.last_message_at = utcnow()
        if title and not chat.title:
            chat.title = title
        return self.save(chat)


class MessageRepository(Repository[Message]):
    """The messages of a chat, and the event lists inside them."""

    def __init__(self, session: Session) -> None:
        super().__init__(Message, session)

    def for_chat(self, chat_id: UUID) -> list[Message]:
        """Every message in order. The list a turn's history is rebuilt from."""
        return self.list(Message.chat_id == chat_id, order_by=col(Message.sequence))

    def next_sequence(self, chat_id: UUID) -> int:
        return self.count(Message.chat_id == chat_id)

    def save(self, obj: Message) -> Message:
        _flag_json(self.session, obj)
        return super().save(obj)

    def add_user_message(
        self, chat: Chat, text: str, attachments: Sequence[Attachment] = ()
    ) -> Message:
        """What was typed, and the files sent with it.

        ``content`` is the typed text alone. Composing the two into what the model reads is
        ``hera_chats.history.compose``, and it happens when a wire message is built — so the
        stored message stays the thing a person actually wrote.
        """
        return self.add(
            Message(
                owner_id=chat.owner_id,
                chat_id=chat.id,
                sequence=self.next_sequence(chat.id),
                role="user",
                content=text,
                attachments=[item.model_dump() for item in attachments],
            )
        )

    def start_assistant_message(self, chat: Chat, *, profile_id: UUID | None = None) -> Message:
        """An empty assistant message, created before the turn runs.

        Created first on purpose: the row is what a resumed turn is appended to, and the
        interface has somewhere to attach a streaming view to. A turn that only got a row on
        success would leave a cancelled answer with nowhere to live.
        """
        return self.add(
            Message(
                owner_id=chat.owner_id,
                chat_id=chat.id,
                sequence=self.next_sequence(chat.id),
                role="assistant",
                profile_id=profile_id if profile_id is not None else chat.profile_id,
            )
        )

    def record(
        self,
        message: Message,
        events: Sequence[ChatEvent],
        *,
        prompt_fingerprint: str = "",
    ) -> Message:
        """Store a turn's events, deriving the visible text from them.

        The event list is the source of truth and ``content`` is derived here — the one place
        it is derived, so a chat list preview and the rendered message can never disagree.
        """
        payload = [CHAT_EVENT_ADAPTER.dump_python(event, mode="json") for event in events]
        message.events = payload
        message.content = visible_text(events)
        if prompt_fingerprint:
            message.prompt_fingerprint = prompt_fingerprint
        return self.save(message)

    def latest_assistant(self, chat_id: UUID) -> Message | None:
        """The most recent assistant message — the one a permission answer resumes."""
        found = self.list(
            Message.chat_id == chat_id,
            Message.role == "assistant",
            order_by=desc(col(Message.sequence)),
            limit=1,
        )
        return found[0] if found else None

    def truncate_from(self, chat_id: UUID, sequence: int) -> int:
        """Remove this message and everything after it, and say how many went.

        What "ask that again" is made of, whether the question was reworded or not: the answer
        that followed the old wording is not an answer to the new one, and leaving it in place
        would have the model reading a conversation that never happened.

        Deleted rather than flagged. A chat *is* its message list, and a ``superseded`` column
        would mean every reader — history, the sidebar preview, the interface — has to remember
        to filter, with the one that forgets showing a version of the conversation nobody had.
        """
        rows = [row for row in self.for_chat(chat_id) if row.sequence >= sequence]
        for row in rows:
            self.session.delete(row)
        self.session.flush()
        return len(rows)

    def delete_for_chat(self, chat_id: UUID) -> int:
        """Remove every message of a chat. Used when the chat itself is deleted."""
        rows = self.for_chat(chat_id)
        for row in rows:
            self.session.delete(row)
        self.session.flush()
        return len(rows)

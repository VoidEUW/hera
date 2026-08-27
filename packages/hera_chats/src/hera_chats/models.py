"""Projects, chats and messages.

A **project** is a container with behaviour, not a folder: a name, its own instructions, its
own pinned skills, and a default profile. ``docs/frontend.md`` holds the line — a *profile*
answers who she is, a project answers what we are working on, and the two compose. Projects
exist from the start because renaming folders into them later would be a migration for nothing;
their v0.2 half is files, which needs embeddings.

A **message** stores its whole event list. That is the record the interface re-renders from at
``done``, and it is why live view and reload cannot disagree.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field

from hera_storage import Entity, SoftDeletable, UTCDateTime

# SQLModel's `sa_column`/`sa_type` want instances although the annotations say otherwise.
_JSON: Any = JSON
_TIMESTAMP: Any = UTCDateTime()

JSON_FIELDS: tuple[str, ...] = ("pinned_skills", "events", "attachments")
"""Columns SQLAlchemy cannot notice an in-place change to.

Same trap as ``hera_profiles.models.JSON_FIELDS``, same fix: the repositories flag these by
name on save. ``sqlalchemy.ext.mutable`` does not work under SQLModel, whose ``__setattr__``
writes the raw value back over SQLAlchemy's coerced one.
"""


class Project(Entity, SoftDeletable, table=True):
    """A body of work, with behaviour of its own."""

    __tablename__ = "chat_projects"

    __table_args__ = (
        UniqueConstraint("owner_id", "slug"),
        Index(None, "created_at", "id"),
    )

    owner_id: UUID = Field(index=True)
    slug: str
    name: str

    instructions: str = ""
    """What we are working on, bound into the prompt's ``project`` slot.

    Prose, not configuration. If a sentence would still be true in a project about something
    else, it belongs in a mind region instead — that is the whole test.
    """

    pinned_skills: list[str] = Field(default_factory=list, sa_column=Column(_JSON))
    """Skills every chat in this project carries. Merged with the profile's pins by the caller;
    a bare list of names, because the router resolves them and reports the ones that are gone."""

    default_profile_id: UUID | None = Field(default=None)
    """Which of her a new chat here starts as. A bare UUID: no cross-package foreign keys."""

    archived: bool = Field(default=False, index=True)


class Chat(Entity, SoftDeletable, table=True):
    """One conversation."""

    __tablename__ = "chat_chats"

    __table_args__ = (Index(None, "created_at", "id"),)

    owner_id: UUID = Field(index=True)

    project_id: UUID | None = Field(default=None, index=True)
    """The project this lives in, or ``None``. A chat outside every project is the normal
    case — it is what the start screen opens."""

    profile_id: UUID | None = Field(default=None)
    """Who answered. Recorded per chat rather than per message: switching profile mid-chat is
    not a thing the composer offers, and a chat whose voice changed halfway is a worse artefact
    than one you have to start again."""

    title: str = ""
    """Empty until the first message names it."""

    last_message_at: datetime | None = Field(default=None, sa_type=_TIMESTAMP, index=True)
    """What the sidebar sorts on. Denormalised deliberately: ordering a chat list by a
    subquery over messages is the query that gets slow first."""

    pinned: bool = Field(default=False, index=True)


class Message(Entity, table=True):
    """One turn, stored as the events it was made of.

    Not soft-deletable. A message is part of a conversation's meaning and removing one changes
    what came after it; the thing a person wants to delete is the chat.
    """

    __tablename__ = "chat_messages"

    __table_args__ = (
        # Every read of a chat is "its messages, in order", so the index carries the order.
        # `chat_id` deliberately does not also carry `index=True`: the naming convention
        # derives an index name from its first column, so a second one on `chat_id` alone
        # resolves to the same name and CREATE INDEX fails at schema creation.
        Index(None, "chat_id", "sequence"),
        Index(None, "created_at", "id"),
    )

    owner_id: UUID = Field(index=True)
    chat_id: UUID

    sequence: int = 0
    """Position in the chat, from zero. Explicit rather than relying on ``created_at``: two
    messages written inside the same millisecond would otherwise have no defined order, and a
    conversation that renders in the wrong order is not a small bug."""

    role: str = "user"
    """``user`` or ``assistant``. A tool result is not a message here — it is an event inside
    the assistant message whose call produced it, which is where it belongs and where the
    interface draws it."""

    content: str = ""
    """The visible text. Authored for a user message; for an assistant message this is
    denormalised from the event list, so a chat list can show a preview without parsing JSON.
    :func:`hera_chats.events.visible_text` is the one place it is derived."""

    events: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(_JSON))
    """The turn, coalesced, as dumped ``ChatEvent`` JSON.

    The source of truth. ``content`` is derived from it, the history sent to the model is
    rebuilt from it, and the interface re-renders from it at ``done`` — which is what makes the
    server render authoritative rather than merely agreed with.
    """

    attachments: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(_JSON))
    """Files sent with a user message: ``name``, ``text``, ``bytes``.

    A field rather than text pasted into ``content``, because the interface has to render them
    as chips and the rule it is built on is that the browser parses nothing. Inlined, the only
    way to draw "a file called notes.md" would be to look for a fence and a filename in the
    prose — a parser, and one that would break the first time somebody wrote about a file.

    The model still receives them inlined; :func:`hera_chats.history.compose` does that when
    the wire message is built, which is the one place it happens.
    """

    profile_id: UUID | None = Field(default=None)
    prompt_fingerprint: str = ""
    """Which prompt produced this, from ``hera_prompts``. Two answers that disagree are much
    easier to explain when you can tell whether they came from the same prompt."""

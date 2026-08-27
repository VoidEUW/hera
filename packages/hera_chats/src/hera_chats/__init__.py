"""hera_chats — projects, chats, the persisted event stream, and the turn orchestrator.

The layer that owns a conversation. It takes a provider, a prompt builder, a skill router and a
tool registry — all injected, none of them named concretely — and turns one message into one
stream of events that is both what the browser renders and what the database keeps.

**Nothing here raises.** A turn closes with a reason rather than throwing, because its consumer
is a Server-Sent Events response and an exception mid-stream is a connection that simply stops.
There is no error module: a 404 for a chat that is not yours belongs to whoever serves HTTP.

A **project** is a container with behaviour: instructions, pinned skills, a default profile.
A **turn** is the loop in ARCHITECTURE.md. A **message** stores the events it was made of,
which is what makes the server render authoritative at ``done``.
"""

from __future__ import annotations

from hera_chats.events import (
    CHAT_EVENT_ADAPTER,
    LIST_ADAPTER,
    ChatEvent,
    CloseReason,
    PermissionDecided,
    PermissionRequired,
    SkillSelected,
    ToolResultEvent,
    TurnClosed,
    coalesce,
    visible_text,
)
from hera_chats.history import (
    Attachment,
    build_history,
    compose,
    content_of,
    events_of,
    says_something,
    turn_to_messages,
)
from hera_chats.models import Chat, Message, Project
from hera_chats.ports import Tools
from hera_chats.repository import (
    ChatRepository,
    MessageRepository,
    ProjectRepository,
    slugify,
    title_from,
)
from hera_chats.settings import ChatsSettings
from hera_chats.turn import Turn, TurnContext, TurnOrchestrator

__all__ = [
    "CHAT_EVENT_ADAPTER",
    "LIST_ADAPTER",
    "Attachment",
    "Chat",
    "ChatEvent",
    "ChatRepository",
    "ChatsSettings",
    "CloseReason",
    "Message",
    "MessageRepository",
    "PermissionDecided",
    "PermissionRequired",
    "Project",
    "ProjectRepository",
    "SkillSelected",
    "ToolResultEvent",
    "Tools",
    "Turn",
    "TurnClosed",
    "TurnContext",
    "TurnOrchestrator",
    "build_history",
    "coalesce",
    "compose",
    "content_of",
    "events_of",
    "says_something",
    "slugify",
    "title_from",
    "turn_to_messages",
    "visible_text",
]

"""What belongs to one person, built when it is first needed (ADR 28).

A person has a mind of their own, memories of their own and permission rules of their own. The
mind and the memories are directories and the builder is cheap, but cloning a mind is a git
command, so the pieces are kept here for a while instead of being rebuilt for every request.
This is the ``Services.for_user`` the ADR names, and the one place that knows where a person's
pieces live.
"""

from __future__ import annotations

import asyncio
import threading
from collections import OrderedDict
from dataclasses import dataclass
from uuid import UUID

from hera_chats import ChatRepository
from hera_core import permission_rules
from hera_home import user_memories_dir, user_mind_dir, user_permissions_path
from hera_memories import MemoriesSettings, MemoryPort, MemoryStore
from hera_permissions import PermissionSet
from hera_profiles import MindRepository, PersonalMind, PromptBuilder
from hera_storage import Database

KEPT = 32
"""How many people's pieces are held at once. A household or a team is well under this; past
it, the person who has been quiet longest is rebuilt from disk when they come back."""


@dataclass(frozen=True)
class Person:
    """One person's mind, the builder over it, and their memories."""

    id: UUID
    mind: PersonalMind
    builder: PromptBuilder
    memories: MemoryStore

    def rules(self) -> PermissionSet:
        """Their own permission rules, read from their file each time — a rule answered on a
        card applies to the very next call, with nothing to invalidate."""
        stored = permission_rules.load(user_permissions_path(str(self.id)))
        return PermissionSet(rules=[item.rule() for item in stored.rules])


class People:
    """Per-person pieces, built on demand and kept for a while."""

    def __init__(
        self,
        template: MindRepository,
        *,
        memories: MemoriesSettings | None = None,
        kept: int = KEPT,
    ) -> None:
        self.template = template
        self._settings = memories or MemoriesSettings()
        self._kept = kept
        self._people: OrderedDict[UUID, Person] = OrderedDict()
        self._building: dict[UUID, threading.Lock] = {}
        self._lock = threading.Lock()

    def get(self, user_id: UUID) -> Person:
        with self._lock:
            found = self._people.get(user_id)
            if found is not None:
                self._people.move_to_end(user_id)
                return found
            building = self._building.setdefault(user_id, threading.Lock())
        # Built under this person's own lock and not the shared one: a first clone runs git, and
        # one person's first visit must not hold up everybody else's turn — while two requests of
        # *theirs* arriving together must not both clone (the second one waits, then finds it).
        with building:
            with self._lock:
                found = self._people.get(user_id)
            if found is not None:
                return found
            person = self._build(user_id)
            with self._lock:
                self._people[user_id] = person
                self._people.move_to_end(user_id)
                while len(self._people) > self._kept:
                    evicted, _ = self._people.popitem(last=False)
                    self._building.pop(evicted, None)
                self._building.pop(user_id, None)
        return person

    def _build(self, user_id: UUID) -> Person:
        mind = PersonalMind(MindRepository(user_mind_dir(str(user_id))), self.template)
        mind.ensure()
        return Person(
            id=user_id,
            mind=mind,
            builder=PromptBuilder(mind),
            memories=MemoryStore(user_memories_dir(str(user_id)), self._settings),
        )


class PersonalMemories:
    """Her ``remember`` and ``forget``, kept in the memories of whoever owns the chat.

    ``hera_mcp`` hands over the conversation the call was part of — from ``_meta``, never from an
    argument (ADR 12) — and the owner of that chat is whose memory it is (ADR 28). A call that
    is not part of a conversation has nobody to belong to, and is refused rather than filed
    under somebody.
    """

    def __init__(self, people: People, database: Database) -> None:
        self._people = people
        self._database = database

    async def remember(
        self,
        key: str,
        text: str,
        *,
        description: str = "",
        why: str = "",
        scope: str = "global",
        chat_id: str = "",
    ) -> str:
        port = await self._port(chat_id)
        return await port.remember(
            key, text, description=description, why=why, scope=scope, chat_id=chat_id
        )

    async def forget(self, key: str, *, chat_id: str = "") -> str:
        return await (await self._port(chat_id)).forget(key, chat_id=chat_id)

    async def _port(self, chat_id: str) -> MemoryPort:
        if not chat_id:
            raise ValueError(
                "a memory belongs to a person, and this call is not part of a conversation"
            )
        owner = await asyncio.to_thread(self._owner, chat_id)
        if owner is None:
            raise ValueError("this conversation does not exist any more")
        person = await asyncio.to_thread(self._people.get, owner)
        return MemoryPort(person.memories)

    def _owner(self, chat_id: str) -> UUID | None:
        try:
            wanted = UUID(chat_id)
        except ValueError:
            return None
        with self._database.session() as session:
            chat = ChatRepository(session).get(wanted)
            return chat.owner_id if chat is not None else None

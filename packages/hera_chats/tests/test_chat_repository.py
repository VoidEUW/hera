"""Projects, chats and messages in the database."""

from __future__ import annotations

from uuid import UUID, uuid4

from hera_chats.models import Message
from sqlmodel import Session

from hera_chats import (
    ChatRepository,
    MessageRepository,
    ProjectRepository,
    TurnClosed,
    slugify,
    title_from,
)
from hera_providers import TextDelta, ThinkingDelta


class TestNaming:
    def test_a_slug_is_url_safe_and_never_empty(self) -> None:
        assert slugify("ChaOS Web!") == "chaos-web"
        assert slugify("???") == "project"

    def test_a_short_message_is_its_own_title(self) -> None:
        assert title_from("Explain Kerberos") == "Explain Kerberos"

    def test_a_long_message_is_cut_on_a_word_boundary(self) -> None:
        """A title ending mid-word looks like a bug rather than like a truncation."""
        title = title_from("word " * 40, limit=20)
        assert title.endswith("…")
        assert "wor…" not in title

    def test_whitespace_is_flattened(self) -> None:
        assert title_from("two\n\nlines   here") == "two lines here"

    def test_one_very_long_word_is_still_cut(self) -> None:
        assert title_from("x" * 200, limit=10) == f"{'x' * 10}…"


class TestProjects:
    def test_a_project_gets_a_free_slug(self, projects: ProjectRepository, owner_id: UUID) -> None:
        assert projects.create(owner_id, "Hera").slug == "hera"
        assert projects.create(owner_id, "Hera").slug == "hera-2"

    def test_archived_projects_are_hidden_by_default(
        self, projects: ProjectRepository, owner_id: UUID
    ) -> None:
        kept = projects.create(owner_id, "Hera")
        gone = projects.create(owner_id, "Old")
        gone.archived = True
        projects.save(gone)

        assert [p.id for p in projects.for_owner(owner_id)] == [kept.id]
        assert len(projects.for_owner(owner_id, include_archived=True)) == 2

    def test_pins_survive_an_in_place_edit(
        self, projects: ProjectRepository, session: Session, owner_id: UUID
    ) -> None:
        """SQLAlchemy cannot see a mutated JSON column on its own; the repository flags it."""
        project = projects.create(owner_id, "Hera")
        project.pinned_skills.append("writing")
        projects.save(project)
        session.expire_all()

        assert projects.get_or_raise(project.id).pinned_skills == ["writing"]

    def test_the_named_setter_needs_no_save(
        self, projects: ProjectRepository, session: Session, owner_id: UUID
    ) -> None:
        project = projects.create(owner_id, "Hera")
        projects.set_pinned_skills(project, ["writing", "tdd"])
        session.expire_all()

        assert projects.get_or_raise(project.id).pinned_skills == ["writing", "tdd"]

    def test_a_third_collision_keeps_counting(
        self, projects: ProjectRepository, owner_id: UUID
    ) -> None:
        for _ in range(2):
            projects.create(owner_id, "Hera")
        assert projects.create(owner_id, "Hera").slug == "hera-3"

    def test_saving_a_detached_project_needs_no_flagging(
        self, projects: ProjectRepository, session: Session, owner_id: UUID
    ) -> None:
        """merge() compares against a freshly loaded row and notices on its own."""
        project = projects.create(owner_id, "Hera")
        project_id = project.id
        session.expunge(project)

        project.pinned_skills = ["writing"]
        projects.save(project)
        session.expire_all()

        assert projects.get_or_raise(project_id).pinned_skills == ["writing"]

    def test_projects_are_scoped_to_their_owner(self, projects: ProjectRepository) -> None:
        projects.create(uuid4(), "Theirs")
        assert projects.for_owner(uuid4()) == []


class TestChats:
    def test_a_loose_chat_is_the_normal_case(self, chats: ChatRepository, owner_id: UUID) -> None:
        """A chat outside every project is what the start screen opens."""
        loose = chats.create(owner_id)
        chats.create(owner_id, project_id=uuid4())

        assert [c.id for c in chats.loose(owner_id)] == [loose.id]

    def test_the_sidebar_orders_by_last_activity(
        self, chats: ChatRepository, owner_id: UUID
    ) -> None:
        old = chats.create(owner_id, title="Old")
        fresh = chats.create(owner_id, title="Fresh")
        chats.touch(old)
        chats.touch(fresh)

        assert [c.title for c in chats.for_owner(owner_id)] == ["Fresh", "Old"]

    def test_a_chat_that_was_never_written_in_still_has_a_place(
        self, chats: ChatRepository, owner_id: UUID
    ) -> None:
        """Sorting on a null would put it at the end instead of at the top where it was
        just created."""
        chats.create(owner_id, title="Empty")
        assert [c.title for c in chats.for_owner(owner_id)] == ["Empty"]

    def test_the_first_message_names_the_chat(self, chats: ChatRepository, owner_id: UUID) -> None:
        chat = chats.create(owner_id)
        chats.touch(chat, title="Explain Kerberos")
        assert chat.title == "Explain Kerberos"

    def test_a_named_chat_is_not_renamed(self, chats: ChatRepository, owner_id: UUID) -> None:
        chat = chats.create(owner_id, title="Chosen by hand")
        chats.touch(chat, title="Something else")
        assert chat.title == "Chosen by hand"

    def test_filtering_by_project(self, chats: ChatRepository, owner_id: UUID) -> None:
        project_id = uuid4()
        inside = chats.create(owner_id, project_id=project_id)
        chats.create(owner_id)

        assert [c.id for c in chats.for_owner(owner_id, project_id=project_id)] == [inside.id]


class TestMessages:
    def test_sequence_counts_up_within_a_chat(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        """Two messages written inside the same millisecond would otherwise have no defined
        order, and a conversation that renders in the wrong order is not a small bug."""
        chat = chats.create(owner_id)
        first = messages.add_user_message(chat, "one")
        second = messages.start_assistant_message(chat)

        assert (first.sequence, second.sequence) == (0, 1)
        assert [m.id for m in messages.for_chat(chat.id)] == [first.id, second.id]

    def test_sequences_are_per_chat(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        one, other = chats.create(owner_id), chats.create(owner_id)
        messages.add_user_message(one, "a")
        assert messages.add_user_message(other, "b").sequence == 0

    def test_recording_derives_the_visible_text(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        """One place it is derived, so a chat list preview and the rendered message can
        never disagree -- and thinking is not part of it."""
        chat = chats.create(owner_id)
        message = messages.start_assistant_message(chat)

        messages.record(
            message,
            [ThinkingDelta(text="hmm"), TextDelta(text="Yes."), TurnClosed()],
            prompt_fingerprint="abc",
        )

        assert message.content == "Yes."
        assert message.prompt_fingerprint == "abc"

    def test_a_recorded_turn_survives_a_reload(
        self, chats: ChatRepository, messages: MessageRepository, session: Session, owner_id: UUID
    ) -> None:
        chat = chats.create(owner_id)
        message = messages.start_assistant_message(chat)
        messages.record(message, [TextDelta(text="Yes."), TurnClosed(reason="completed")])
        session.expire_all()

        reloaded = messages.get_or_raise(message.id)
        assert [event["type"] for event in reloaded.events] == ["text_delta", "turn_closed"]

    def test_recording_twice_replaces_rather_than_appends(
        self, chats: ChatRepository, messages: MessageRepository, session: Session, owner_id: UUID
    ) -> None:
        """A resumed turn hands back the whole list, inherited events included."""
        chat = chats.create(owner_id)
        message = messages.start_assistant_message(chat)
        messages.record(message, [TextDelta(text="one")])
        messages.record(message, [TextDelta(text="one"), TextDelta(text="two")])
        session.expire_all()

        assert len(messages.get_or_raise(message.id).events) == 2

    def test_the_latest_assistant_message_is_what_a_card_resumes(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        chat = chats.create(owner_id)
        messages.start_assistant_message(chat)
        messages.add_user_message(chat, "again")
        newest = messages.start_assistant_message(chat)

        found = messages.latest_assistant(chat.id)
        assert found is not None and found.id == newest.id

    def test_there_is_no_latest_assistant_in_an_empty_chat(
        self, chats: ChatRepository, owner_id: UUID, messages: MessageRepository
    ) -> None:
        assert messages.latest_assistant(chats.create(owner_id).id) is None

    def test_deleting_a_chats_messages(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        chat = chats.create(owner_id)
        messages.add_user_message(chat, "a")
        messages.add_user_message(chat, "b")

        assert messages.delete_for_chat(chat.id) == 2
        assert messages.for_chat(chat.id) == []

    def test_an_assistant_message_inherits_the_chats_profile(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        profile_id = uuid4()
        chat = chats.create(owner_id, profile_id=profile_id)
        assert messages.start_assistant_message(chat).profile_id == profile_id

    def test_an_explicit_profile_wins(
        self, chats: ChatRepository, messages: MessageRepository, owner_id: UUID
    ) -> None:
        other = uuid4()
        chat = chats.create(owner_id, profile_id=uuid4())
        assert messages.start_assistant_message(chat, profile_id=other).profile_id == other


class TestTheTables:
    def test_every_table_carries_the_package_prefix(self) -> None:
        """All models share one MetaData, so an unprefixed name from two packages would
        silently collide."""
        from hera_chats import Chat, Project

        assert Project.__tablename__ == "chat_projects"
        assert Chat.__tablename__ == "chat_chats"
        assert Message.__tablename__ == "chat_messages"

    def test_messages_index_the_order_they_are_read_in(self) -> None:
        table = Message.metadata.tables["chat_messages"]
        indexed = {tuple(column.name for column in index.columns) for index in table.indexes}
        assert ("chat_id", "sequence") in indexed

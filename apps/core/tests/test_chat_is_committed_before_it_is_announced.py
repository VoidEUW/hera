"""A row the response names has to be committed before the response goes out.

``create_chat`` mints an id and hands it back in a ``201``, and the browser's next move is to
read that id straight back — the start screen creates the chat, navigates to it, and the chat
route loads it. So a ``201`` is a claim about the database, and it has to be true by the time it
arrives.

It was not. The commit lives in the teardown of a ``yield`` dependency
(``hera_storage.database.session``), and FastAPI runs that teardown *after* the response is
sent — so the row was still uncommitted when the client asked for it, and about one request in
eight came back ``404 no such chat``. A new chat would open empty, and the sentence typed into
the start screen was never sent. [#136](https://github.com/VoidEUW/hera/issues/136)

**Why this test does not go through HTTP.** The suite's client is an ``ASGITransport``, which
runs the whole ASGI call — response *and* dependency teardown — inside a single ``await``. The
window this is about exists between those two, so an HTTP test cannot see it and would pass
against the broken code. Asserting the invariant directly is the only way to pin it down.
"""

from __future__ import annotations

from uuid import UUID

from hera_chats import ChatRepository
from hera_core.api.chats import create_chat
from hera_core.schemas import ChatIn
from hera_core.wiring import Services


def _see_it_from_another_connection(services: Services, chat_id: UUID) -> bool:
    """Whether a *different* connection can see the chat.

    A second session on this database gets a second connection from the pool — which is what the
    browser's next request gets, and the reason the fixture uses a file rather than
    ``Database.in_memory()`` (see ``conftest.py``: an in-memory database shares one connection
    through a ``StaticPool``, and a second session there would see uncommitted rows and pass
    against the bug). A pooled connection can only ever see what has been committed.
    """
    with services.database.session() as probe:
        return ChatRepository(probe).get(chat_id) is not None


class TestAChatIsCommittedBeforeItIsAnnounced:
    def test_the_row_is_durable_before_the_201_goes_out(self, services: Services) -> None:
        owner = services.settings.owner_id

        # The route called directly, so the unit of work is still open: the `with` block has not
        # exited, and exiting it is what used to be the commit.
        with services.database.session() as session:
            announced = create_chat(ChatIn(), owner, session)

            assert _see_it_from_another_connection(services, announced.id), (
                "create_chat returned an id for a row that is not committed yet. Anything that "
                "reads that id in the next instant gets a 404 -- which is what opening a chat "
                "from the start screen does, every time."
            )

    def test_the_seeded_default_profile_is_part_of_the_same_commit(
        self, services: Services
    ) -> None:
        """The fallback profile is read rather than written, but it travels in the response too.

        A reader that could see the row and not the profile it was created with would render a
        different conversation from the one that was announced, which is the same class of lie
        from a different field.
        """
        # Values, not mapped instances: a `Chat` does not survive its session, and touching one
        # afterwards raises rather than quietly answering something else.
        with services.database.session() as session:
            announced = create_chat(ChatIn(), services.settings.owner_id, session)
            chat_id, announced_profile = announced.id, announced.profile_id

        with services.database.session() as probe:
            stored_profile = ChatRepository(probe).get(chat_id)
            seen = None if stored_profile is None else stored_profile.profile_id

        assert seen == announced_profile

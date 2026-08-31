"""Fixtures for the application suite.

The whole application, against `FakeProvider` and a scripted tool layer. That is what ADR 6
means by testing splitting cleanly: `httpx` drives the real ASGI app, so the routes, the
dependency graph, the SSE framing and the persistence are all exercised — and none of it needs
a model or an MCP server.

Everything that touches disk is pointed at a temporary directory, and `HERA_HOME` is repointed
for every test. Nothing here may write into a real `~/.hera`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID

import pytest
from core_support import API, StubTools, WriteSkill  # noqa: F401
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hera_chats import ChatsSettings, TurnOrchestrator
from hera_core.app import create_app

# Registers every table into the shared MetaData before `create_all` runs.
from hera_core.models import ALL_TABLES  # noqa: F401
from hera_core.settings import CoreSettings
from hera_core.wiring import Services
from hera_mcp import ASK_TOOL, BUILTIN_SERVER_NAME, CHAT_ID_META
from hera_memories import MemoryStore
from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_profiles import MindRepository, ProfileRepository, PromptBuilder
from hera_providers import FakeProvider
from hera_skillsets import SkillLibrary, SkillRouter
from hera_storage import Database, StorageSettings


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERA_HOME", str(tmp_path / "home"))


@pytest.fixture
def owner_id() -> UUID:
    return CoreSettings().owner_id


@pytest.fixture
def skills_path(tmp_path: Path) -> Path:
    path = tmp_path / "skills"
    path.mkdir()
    return path


@pytest.fixture
def write_skill(skills_path: Path) -> WriteSkill:
    def write(skill_id: str, *, description: str = "Does a thing.", body: str = "Do it.") -> Path:
        directory = skills_path / skill_id
        directory.mkdir(parents=True, exist_ok=True)
        directory.joinpath("SKILL.md").write_text(
            f"---\nname: {skill_id}\ndescription: {description}\n---\n{body}\n", encoding="utf-8"
        )
        return directory

    return write


@pytest.fixture
def provider() -> FakeProvider:
    """Scripted by default with a single plain answer. Reassign ``_turns`` in a test that
    needs something else, or build a new one and pass it to ``make_services``."""
    return FakeProvider()


@pytest.fixture
def tools() -> StubTools:
    return StubTools()


@pytest.fixture
def ask_policy() -> Policy:
    return Policy(
        base=PermissionSet(
            rules=[Rule(pattern="fs__*", decision=Decision.ASK, reason="it writes to disk")]
        ),
        fallback=Decision.ALLOW,
    )


@pytest.fixture
def make_services(tmp_path: Path, skills_path: Path) -> Iterator[object]:
    """Build a container the way ``build_services`` does, with everything faked.

    Deliberately not calling ``build_services``: that one reads ``mcp.json`` and would open
    real subprocesses. The shape is the same, and ``test_wiring.py`` checks the real one
    against it.
    """
    built: list[Services] = []
    made = 0

    def make(
        provider: FakeProvider | None = None,
        registry: StubTools | None = None,
    ) -> Services:
        nonlocal made
        made += 1
        # A file, not Database.in_memory(). In-memory SQLite uses a StaticPool -- one
        # connection shared by every session -- so a second session sees the first's
        # *uncommitted* rows. That hid a real bug: the streaming route was persisting a turn
        # into a transaction nobody had committed, which worked in memory and lost the whole
        # answer against a file. The suite has to be able to tell those apart.
        database = Database(StorageSettings(url=f"sqlite:///{tmp_path / f'hera-{made}.sqlite3'}"))
        database.create_all()
        mind = MindRepository(tmp_path / "mind")
        mind.ensure()
        library = SkillLibrary(skills_path)
        builder = PromptBuilder(mind)
        router = SkillRouter(library)
        # Its own directory per container, so a test that remembers something cannot be read
        # by the next one -- and so nothing here ever touches a real ~/.hera/memories.
        memories = MemoryStore(tmp_path / f"memories-{made}")
        settings = CoreSettings()
        used = provider if provider is not None else FakeProvider()

        with database.session() as session:
            ProfileRepository(session).ensure_default_exists(settings.owner_id)

        container = Services(
            settings=settings,
            database=database,
            mind=mind,
            builder=builder,
            library=library,
            router=router,
            memories=memories,
            registry=registry,  # type: ignore[arg-type]  # StubTools satisfies the Tools port
            provider=used,
            orchestrator=TurnOrchestrator(
                provider=used,
                builder=builder,
                router=router,
                registry=registry,
                # Named the way `build_services` names it, so the asking path is exercised
                # here rather than only in `hera_chats`' own suite. `test_wiring.py` holds
                # this container's shape against the real one.
                settings=ChatsSettings(
                    model="fake-model",
                    max_iterations=4,
                    asking_tools=(f"{BUILTIN_SERVER_NAME}__{ASK_TOOL}",),
                    # Both of these are filled in from `hera_mcp` by `hera_core.wiring`, and
                    # both have to be here for the same reason: this fixture builds a
                    # `Services` by hand rather than calling `build_services`, so anything the
                    # real wiring configures is something this can silently be missing.
                    chat_meta_key=CHAT_ID_META,
                ),
            ),
        )
        built.append(container)
        return container

    yield make
    for container in built:
        container.database.dispose()


@pytest.fixture
def services(make_services: object) -> Services:
    return make_services()  # type: ignore[operator]  # the factory above


@pytest.fixture
def app(services: Services, tmp_path: Path) -> FastAPI:
    """The API with no interface behind it.

    Pointed at an empty directory on purpose: whether `npm run build` has been run is not
    something an API test should depend on, and a suite that passes only on a machine that
    happens to have built the front end is a suite that fails in CI for a reason nobody can
    see.
    """
    settings = services.settings.model_copy(update={"static_dir": str(tmp_path / "no-build")})
    return create_app(settings, services=services)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """An httpx client bound to the ASGI app, with the lifespan run.

    ``LifespanManager`` is not used and not needed: ``create_app`` was given a container, so
    the lifespan only has to attach it — which this does by hand, keeping the suite free of
    another dependency.
    """
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://hera.test") as http,
        app.router.lifespan_context(app),
    ):
        yield http

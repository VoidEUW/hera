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
from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_profiles import MindRepository, ProfileRepository, PromptBuilder
from hera_providers import FakeProvider
from hera_skillsets import SkillLibrary, SkillRouter
from hera_storage import Database


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

    def make(
        provider: FakeProvider | None = None,
        registry: StubTools | None = None,
    ) -> Services:
        database = Database.in_memory()
        database.create_all()
        mind = MindRepository(tmp_path / "mind")
        mind.ensure()
        library = SkillLibrary(skills_path)
        builder = PromptBuilder(mind)
        router = SkillRouter(library)
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
            registry=registry,  # type: ignore[arg-type]  # StubTools satisfies the Tools port
            provider=used,
            orchestrator=TurnOrchestrator(
                provider=used,
                builder=builder,
                router=router,
                registry=registry,
                settings=ChatsSettings(model="fake-model", max_iterations=4),
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
def app(services: Services) -> FastAPI:
    return create_app(services.settings, services=services)


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

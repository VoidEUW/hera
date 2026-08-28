"""Fixtures for the chats suite.

Everything real except the model and the MCP servers. The mind is a genuine git repository in
a temporary directory, the skills are genuine files, the database is genuine SQLite — because
the bugs this package can have are about *ordering* and *what is persisted*, and a mocked
repository would answer questions the real one does not.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from chat_support import StubTools, WriteSkill

# Importing the models registers chat_* into SQLModel.metadata, which is what the `db` fixture
# from hera_storage creates tables from.
from hera_chats.models import Message, Project  # noqa: F401
from sqlmodel import Session

from hera_chats import (
    Chat,
    ChatRepository,
    ChatsSettings,
    MessageRepository,
    ProjectRepository,
    TurnOrchestrator,
)
from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_profiles import MindRepository, Profile, PromptBuilder
from hera_providers import FakeProvider
from hera_skillsets import SkillLibrary, SkillRouter


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERA_HOME", str(tmp_path / "home"))


@pytest.fixture
def owner_id() -> UUID:
    return uuid4()


@pytest.fixture
def mind(tmp_path: Path) -> MindRepository:
    repository = MindRepository(tmp_path / "mind")
    repository.ensure()
    return repository


@pytest.fixture
def builder(mind: MindRepository) -> PromptBuilder:
    return PromptBuilder(mind)


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
def router(skills_path: Path) -> SkillRouter:
    return SkillRouter(SkillLibrary(skills_path))


@pytest.fixture
def profile(owner_id: UUID) -> Profile:
    return Profile(owner_id=owner_id, slug="hera", name="Hera")


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
def settings() -> ChatsSettings:
    # `asking_tools` names a tool on a server this package cannot see, which is the point of
    # the setting: the application fills it in from `hera_mcp.ASK_TOOL`. A made-up name here
    # would be just as valid — what is under test is that the *name* suspends the turn.
    return ChatsSettings(model="fake-model", max_iterations=4, asking_tools=("hera__ask",))


@pytest.fixture
def make_orchestrator(
    builder: PromptBuilder, router: SkillRouter, settings: ChatsSettings
) -> object:
    def make(provider: FakeProvider, registry: StubTools | None = None) -> TurnOrchestrator:
        return TurnOrchestrator(
            provider=provider,
            builder=builder,
            router=router,
            registry=registry,
            settings=settings,
        )

    return make


@pytest.fixture
def projects(session: Session) -> ProjectRepository:
    return ProjectRepository(session)


@pytest.fixture
def chats(session: Session) -> ChatRepository:
    return ChatRepository(session)


@pytest.fixture
def messages(session: Session) -> MessageRepository:
    return MessageRepository(session)


@pytest.fixture
def chat(chats: ChatRepository, owner_id: UUID) -> Chat:
    return chats.create(owner_id)

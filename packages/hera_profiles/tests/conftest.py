"""Fixtures for the profiles suite.

Every fixture here points at a temporary directory. Nothing in this package may touch a real
``~/.hera`` during a test run, and the cheapest way to guarantee that is to never let the
default path be reached: ``HERA_HOME`` is repointed for the whole session as well, so a test
that forgets to pass a path still writes somewhere harmless.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest

# Importing the model registers profile_profiles into SQLModel.metadata, which is what the
# `db` fixture from hera_storage creates tables from.
from hera_profiles.models import Profile  # noqa: F401
from sqlmodel import Session

from hera_profiles import MindRepository, ProfileRepository, PromptBuilder


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERA_HOME", str(tmp_path / "home"))


@pytest.fixture
def mind(tmp_path: Path) -> Iterator[MindRepository]:
    """A seeded mind repository in its own directory."""
    repository = MindRepository(tmp_path / "mind")
    repository.ensure()
    yield repository


@pytest.fixture
def bare_mind(tmp_path: Path) -> MindRepository:
    """A mind repository that has never been initialised."""
    return MindRepository(tmp_path / "bare")


@pytest.fixture
def builder(mind: MindRepository) -> PromptBuilder:
    return PromptBuilder(mind)


@pytest.fixture
def owner_id() -> UUID:
    return uuid4()


@pytest.fixture
def profiles(session: Session) -> ProfileRepository:
    return ProfileRepository(session)

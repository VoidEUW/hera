"""``~/.hera/config.toml`` — the settings a person edits, and the ones the interface writes.

A file rather than a table, for the reason ``ARCHITECTURE.md`` already lists it as one: there
must be nothing in ``~/.hera`` you cannot open in an editor. A provider you configured through
the interface is a provider you can also read, diff and copy to another machine, and a
misconfigured endpoint is something you can fix with ``vim`` when the interface will not start
because of it.

**Where an endpoint comes from.** Each library keeps reading its own ``HERA_*`` environment
variables, and this file **seeds itself from them** the first time it is written — so an
existing ``HERA_PROVIDER_BASE_URL`` is what you find already filled in rather than something
the interface silently ignores. After that the file wins, because a setting you can change on
screen that quietly does not apply is worse than one that overrides a variable.

**Several providers, one active.** ADR 2 fixes the *model family* the prompt is written for; it
says nothing about how many endpoints you may save. Running LM Studio on one port and something
else on another and switching between them is ordinary, and a list with an active entry costs
almost nothing over a single set of fields.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, field_validator

from hera_home import config_path
from hera_providers import ProviderSettings

SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-_")


def validate_provider_name(name: str) -> str:
    """Lowercase, digits, ``-`` and ``_``. Raises ``ValueError`` otherwise.

    Shared with the request schema rather than only enforced here: a rule the API model does
    not know about surfaces as a 500 from inside the handler instead of a 422 telling the
    person what a name may contain.
    """
    cleaned = name.strip().lower()
    if not cleaned or set(cleaned) - SLUG_CHARS:
        raise ValueError("a provider name uses lowercase letters, digits, - and _")
    return cleaned


class ProviderEntry(BaseModel):
    """One endpoint she can be pointed at."""

    model_config = ConfigDict(frozen=True)

    name: str
    """What you call it. Also the identifier in the URL, so it is kept URL-safe."""

    base_url: str = "http://localhost:1234/v1"
    api_key: str = ""
    """Empty for a local server, which is the intended deployment. Never sent to the browser —
    :meth:`redacted` is what the API returns."""

    model: str = "qwen3.6-35b"
    embedding_model: str = ""
    """Empty means embeddings are off and retrieval falls back to keyword overlap (ADR 5)."""

    timeout_s: float = 180.0
    connect_timeout_s: float = 5.0

    @field_validator("name")
    @classmethod
    def _usable_name(cls, name: str) -> str:
        return validate_provider_name(name)

    def settings(self) -> ProviderSettings:
        """As ``hera_providers`` wants it."""
        return ProviderSettings(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            embedding_model=self.embedding_model,
            timeout_s=self.timeout_s,
            connect_timeout_s=self.connect_timeout_s,
        )

    def redacted(self) -> dict[str, Any]:
        """For the API. The key never leaves the machine it was typed on.

        ``api_key_set`` rather than a masked string, because a row of asterisks is something a
        person will try to edit and something a client will try to send back.
        """
        data = self.model_dump()
        data.pop("api_key")
        data["api_key_set"] = bool(self.api_key)
        return data


class HeraConfig(BaseModel):
    """Everything in ``config.toml``."""

    model_config = ConfigDict(frozen=True)

    providers: list[ProviderEntry] = Field(default_factory=list)
    active_provider: str = ""

    def active(self) -> ProviderEntry | None:
        """The endpoint she is pointed at, or the first one, or nothing.

        Falling back to the first rather than to nothing: an ``active_provider`` naming an
        entry somebody deleted by hand should not leave a working install with no model.
        """
        for entry in self.providers:
            if entry.name == self.active_provider:
                return entry
        return self.providers[0] if self.providers else None

    def get(self, name: str) -> ProviderEntry | None:
        return next((entry for entry in self.providers if entry.name == name), None)

    def with_provider(self, entry: ProviderEntry) -> HeraConfig:
        """Add or replace one entry, keeping the order stable."""
        replaced = [
            entry if existing.name == entry.name else existing for existing in self.providers
        ]
        if all(existing.name != entry.name for existing in self.providers):
            replaced = [*self.providers, entry]
        active = self.active_provider or entry.name
        return HeraConfig(providers=replaced, active_provider=active)

    def without(self, name: str) -> HeraConfig:
        remaining = [entry for entry in self.providers if entry.name != name]
        active = self.active_provider
        if active == name:
            active = remaining[0].name if remaining else ""
        return HeraConfig(providers=remaining, active_provider=active)

    def activated(self, name: str) -> HeraConfig:
        return HeraConfig(providers=list(self.providers), active_provider=name)


def load(path: Path | None = None) -> HeraConfig:
    """Read the file, seeding it from the environment when there is nothing in it yet.

    A fresh install has no file and the environment's defaults describe the intended
    deployment — a local OpenAI-compatible server, one Qwen model — so what a person finds on
    the Models screen is already the right shape to correct rather than an empty form.
    """
    path = path if path is not None else config_path()
    if not path.is_file():
        return HeraConfig(providers=[_from_environment()], active_provider="local")

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path} could not be read: {exc}") from exc

    try:
        config = HeraConfig.model_validate(raw)
    except ValueError as exc:
        raise ConfigError(f"{path} is not a valid Hera configuration: {exc}") from exc

    if not config.providers:
        return HeraConfig(providers=[_from_environment()], active_provider="local")
    return config


def save(config: HeraConfig, path: Path | None = None) -> None:
    """Write the file, creating the directory if it is not there yet.

    Written whole and replaced atomically. A half-written ``config.toml`` is a Hera that will
    not start, and the moment it happens is the moment somebody was changing the endpoint
    because the old one had stopped working.
    """
    path = path if path is not None else config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = tomli_w.dumps(config.model_dump(mode="python"))
    temporary = path.with_suffix(f"{path.suffix}.writing")
    temporary.write_text(_HEADER + body, encoding="utf-8")
    temporary.replace(path)


class ConfigError(RuntimeError):
    """``config.toml`` exists and cannot be used.

    Not caught anywhere: a person who has hand-edited the file into a state that will not parse
    needs the parser's own complaint, not a default quietly taking its place.
    """


_HEADER = """# Hera's settings. Edited by the interface, and safe to edit by hand.
#
# Each library also reads its own HERA_* environment variables; this file is seeded from them
# once and wins afterwards, so what you change on screen is what applies.

"""


def _from_environment() -> ProviderEntry:
    settings = ProviderSettings()
    return ProviderEntry(
        name="local",
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.model,
        embedding_model=settings.embedding_model,
        timeout_s=settings.timeout_s,
        connect_timeout_s=settings.connect_timeout_s,
    )

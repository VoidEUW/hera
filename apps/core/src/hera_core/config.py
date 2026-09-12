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
from typing import Any, Literal

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


ProviderKind = Literal[
    "openai",
    "anthropic",
    "google",
    "mistral",
    "openrouter",
    "lmstudio",
    "ollama",
    "vllm",
    "llamacpp",
    "generic",
    "custom",
]
"""Who an endpoint is, for the small icon beside its name. Manual rather than guessed from
``base_url``: these are arbitrary self-hosted OpenAI-compatible servers, and a hostname is not
a reliable way to tell LM Studio from vLLM from a proxy in front of either. ``custom`` is the
one kind that carries an uploaded image instead of a bundled one — see
:attr:`ProviderEntry.logo_media_type`."""


class ModelEntry(BaseModel):
    """One named model registered against an endpoint."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    """What travels in the request body's ``model`` field — has to match what the endpoint
    calls it."""

    name: str = ""
    """The friendly label shown on screen. Empty is filled in with :attr:`id` below, so nothing
    that reads a model entry has to fall back itself."""

    options: dict[str, Any] = Field(default_factory=dict)
    """Request-body fields this model's server understands and Hera does not.

    Merged into the body last, through ``ChatsSettings.extra`` and
    ``hera_providers.ChatRequest.extra``. Registered per *model* rather than per endpoint
    because that is the grain the need has: the same OpenRouter URL serves GLM-4.7, which wants
    ``chat_template_kwargs.clear_thinking = false`` so it keeps earlier turns' reasoning when it
    renders the history, and GLM5.3, which wants nothing.

    Empty for almost everything, and deliberately not a schema — the whole point is that this
    package does not know what a given server accepts. What it *does* refuse is a key that would
    overwrite the request rather than add to it; that check lives in ``hera_core.schemas``, at
    the edge where a person's input arrives.
    """

    @model_validator(mode="before")
    @classmethod
    def _default_name(cls, data: object) -> object:
        """A ``mode="after"`` validator that returns a *different* instance is silently a no-op
        when a model is constructed via ``__init__`` rather than ``model_validate`` — pydantic
        only applies that return value on the ``model_validate`` path. Doing the fallback here,
        on the raw input, works on both."""
        if isinstance(data, dict) and not data.get("name") and data.get("id"):
            return {**data, "name": data["id"]}
        return data


class ProviderEntry(BaseModel):
    """One endpoint she can be pointed at, and the named models registered on it."""

    model_config = ConfigDict(frozen=True)

    name: str
    """What you call it. Also the identifier in the URL, so it is kept URL-safe."""

    kind: ProviderKind = "generic"

    base_url: str = "http://localhost:1234/v1"
    api_key: str = ""
    """Empty for a local server, which is the intended deployment. Never sent to the browser —
    :meth:`redacted` is what the API returns."""

    models: list[ModelEntry] = Field(default_factory=list)
    active_model: str = ""
    """Which of :attr:`models` is currently selected. Kept consistent with ``models`` by
    :meth:`_valid_active_model` rather than trusted at face value — a person can delete the file's
    active model by hand without also fixing this field."""

    logo_media_type: str = ""
    """Set only when ``kind == "custom"`` and an upload has succeeded. Empty means "no custom
    logo" — the same empty-string-means-off convention as :attr:`embedding_model` and
    :attr:`api_key`, not ``None``, so it round-trips through TOML with no special-casing in
    :func:`_writable`."""

    embedding_model: str = ""
    """Empty means embeddings are off and retrieval falls back to keyword overlap (ADR 5)."""

    timeout_s: float = 600.0
    """How long this endpoint may be **silent** before the turn gives up — not how long a turn
    may take. See :attr:`hera_providers.ProviderSettings.timeout_s`: on a streamed answer it is
    measured between one piece of the response and the next, so what it really bounds is loading
    the weights and prefilling the prompt. Editable on Settings → Models, because the right value
    is a fact about the machine the model is on and nobody else can know it."""

    connect_timeout_s: float = 5.0

    @field_validator("name")
    @classmethod
    def _usable_name(cls, name: str) -> str:
        return validate_provider_name(name)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: object) -> object:
        """Two things, done together and both on the raw input — not as an ``after`` validator,
        which is silently a no-op on the ``__init__`` path when it returns a different instance
        (only ``model_validate`` applies that return value; every route in this app constructs
        ``ProviderEntry`` directly via keyword arguments).

        **Migrating an old file.** Old files (and old call sites) said ``model: str``. New ones
        say ``models`` + ``active_model``. A permanent read-time normalization, not a one-off
        migration script — every load handles both shapes forever, the same stance
        :data:`TUNING_FIELDS` already takes on old/new default drift in this file.

        **Keeping ``active_model`` honest.** A person can hand-edit ``active_model`` to a model
        that was never registered, or that has since been removed — falls back to the first
        registered model, the same defensive stance as :meth:`HeraConfig.active`.
        """
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "models" not in data:
            bare = data.pop("model", None)
            if bare:
                data["models"] = [{"id": bare, "name": bare}]
                data["active_model"] = bare

        def model_id(entry: object) -> str:
            if isinstance(entry, dict):
                # A missing id normalizes to "" rather than raising here — a `KeyError` would
                # escape `load()`'s `ValueError`-only handling as a 500. Left this way, it fails
                # `min_length=1` on `ModelEntry.id` instead, which does become a `ConfigError`.
                return str(entry.get("id") or "")
            return entry.id  # type: ignore[attr-defined,no-any-return]

        models = data.get("models") or []
        ids = {model_id(m) for m in models}
        active = data.get("active_model") or ""
        if models and active not in ids:
            data["active_model"] = model_id(models[0])
        elif not models and active:
            data["active_model"] = ""
        return data

    def settings(self) -> ProviderSettings:
        """As ``hera_providers`` wants it."""
        return ProviderSettings(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.active_model,
            embedding_model=self.embedding_model,
            timeout_s=self.timeout_s,
            connect_timeout_s=self.connect_timeout_s,
        )

    def active_options(self) -> dict[str, Any]:
        """The request options of whichever model is active here, or none.

        Not on :meth:`settings` alongside the rest: ``ProviderSettings`` is where a request goes
        and how long it may take, and ``hera_providers`` has no business holding a bag of fields
        it will not read. These reach the wire through ``ChatsSettings.extra``, which is the
        layer that assembles a request.
        """
        for model in self.models:
            if model.id == self.active_model:
                return dict(model.options)
        return {}

    def redacted(self) -> dict[str, Any]:
        """For the API. The key never leaves the machine it was typed on.

        ``api_key_set`` rather than a masked string, because a row of asterisks is something a
        person will try to edit and something a client will try to send back.
        """
        data = self.model_dump()
        data.pop("api_key")
        data["api_key_set"] = bool(self.api_key)
        return data

    def with_model(self, model: ModelEntry) -> ProviderEntry:
        """Register a model, or replace the one already registered under that id.

        The first one registered becomes active — the model-level echo of "the first provider
        added becomes active" on :meth:`HeraConfig.with_provider`.
        """
        if any(m.id == model.id for m in self.models):
            replaced = [model if m.id == model.id else m for m in self.models]
        else:
            replaced = [*self.models, model]
        return self.model_copy(
            update={"models": replaced, "active_model": self.active_model or model.id}
        )

    def without_model(self, model_id: str) -> ProviderEntry:
        """Drop one model. If it was active, another registered one takes over — or none does,
        if that was the last."""
        remaining = [m for m in self.models if m.id != model_id]
        active = self.active_model
        if active == model_id:
            active = remaining[0].id if remaining else ""
        return self.model_copy(update={"models": remaining, "active_model": active})

    def with_active_model(self, model_id: str) -> ProviderEntry:
        if model_id not in {m.id for m in self.models}:
            raise ValueError(f"no model called {model_id!r} on {self.name!r}")
        return self.model_copy(update={"active_model": model_id})


class HeraConfig(BaseModel):
    """Everything in ``config.toml``."""

    model_config = ConfigDict(frozen=True)

    providers: list[ProviderEntry] = Field(default_factory=list)
    active_provider: str = ""

    timezone: str = ""
    """Where the person is, as an IANA name — ``Europe/Berlin``, not an offset.

    A name rather than ``+02:00`` because an offset is wrong twice a year, and the turn that
    happens on the last Sunday in October should not be an hour out. Empty means the prompt
    carries UTC alone, which is the honest default for a deployment nobody has told where it
    is: the *server's* zone and the *person's* are different questions, and a self-hosted Hera
    may well be on a box in another country.
    """

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
        return HeraConfig(providers=replaced, active_provider=active, timezone=self.timezone)

    def without(self, name: str) -> HeraConfig:
        remaining = [entry for entry in self.providers if entry.name != name]
        active = self.active_provider
        if active == name:
            active = remaining[0].name if remaining else ""
        return HeraConfig(providers=remaining, active_provider=active, timezone=self.timezone)

    def with_timezone(self, timezone: str) -> HeraConfig:
        return HeraConfig(
            providers=list(self.providers), active_provider=self.active_provider, timezone=timezone
        )

    def activated(self, name: str) -> HeraConfig:
        return HeraConfig(
            providers=list(self.providers), active_provider=name, timezone=self.timezone
        )


def load(path: Path | None = None) -> HeraConfig:
    """Read the file, seeding it from the environment when there is nothing in it yet.

    A fresh install has no file and the environment's defaults describe the intended
    deployment — a local OpenAI-compatible server, one Qwen model — so what a person finds on
    the Models screen is already the right shape to correct rather than an empty form.
    """
    path = path if path is not None else config_path()
    if not path.is_file():
        return HeraConfig(providers=[_seeded_from_environment()], active_provider="local")

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path} could not be read: {exc}") from exc

    try:
        config = HeraConfig.model_validate(raw)
    except ValueError as exc:
        raise ConfigError(f"{path} is not a valid Hera configuration: {exc}") from exc

    if not config.providers:
        # Seeded, but the rest of the file is kept: a person who deleted every endpoint by hand
        # should not also lose the timezone they set on the screen above it.
        return HeraConfig(
            providers=[_seeded_from_environment()],
            active_provider="local",
            timezone=config.timezone,
        )
    return config


def _seeded_from_environment() -> ProviderEntry:
    """:func:`_from_environment`, wrapped the same way ``model_validate`` is above.

    An environment variable is still a person's hand-edited input — ``HERA_PROVIDER_MODEL=""``
    reaches :class:`ModelEntry` as an empty id, since ``pydantic-settings`` does not treat an
    empty value as unset. That should read as a wrong deployment, not a 500.
    """
    try:
        return _from_environment()
    except ValueError as exc:
        raise ConfigError(f"the environment describes an invalid provider: {exc}") from exc


def save(config: HeraConfig, path: Path | None = None) -> None:
    """Write the file, creating the directory if it is not there yet.

    Written whole and replaced atomically. A half-written ``config.toml`` is a Hera that will
    not start, and the moment it happens is the moment somebody was changing the endpoint
    because the old one had stopped working.

    Not every field is written — see :data:`TUNING_FIELDS`.
    """
    path = path if path is not None else config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = tomli_w.dumps(_writable(config))
    temporary = path.with_suffix(f"{path.suffix}.writing")
    temporary.write_text(_HEADER + body, encoding="utf-8")
    temporary.replace(path)


TUNING_FIELDS = ("timeout_s", "connect_timeout_s")
"""Fields written **only when they differ from the default**.

The rest of an entry is written whether or not it was changed, because the rest of an entry is
what you came to the file to read: an endpoint with no ``base_url`` in it is a worse file even
when the URL is the default one.

These two are different, and the difference cost a real afternoon. The file is *seeded* from the
environment on first run and every field is dumped, so it records the defaults of whichever
version happened to write it first — and the file wins afterwards. That means a default this
project later improves is silently dead for everybody who has already run Hera, which is the
opposite of what "the file wins" is supposed to protect. It surfaced as a turn ending in *did
not answer in time* on an install whose ``timeout_s = 180.0`` nobody had ever chosen.

Omitting them unless they were set makes the file mean *what I decided* rather than *what the
defaults were the day I installed it*. A value a person actually sets is written and still wins;
one they never touched follows the project. What it costs is that the file no longer lists every
knob — which is why the Models screen shows the effective value in a field rather than leaving
it to be discovered.
"""


def _writable(config: HeraConfig) -> dict[str, Any]:
    """The document as it goes to disk. See :data:`TUNING_FIELDS`."""
    document = config.model_dump(mode="python")
    blank = ProviderEntry(name="seed")
    for entry, dumped in zip(config.providers, document["providers"], strict=True):
        for field in TUNING_FIELDS:
            if getattr(entry, field) == getattr(blank, field):
                dumped.pop(field, None)
    return document


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
        models=[ModelEntry(id=settings.model, name=settings.model)],
        active_model=settings.model,
        embedding_model=settings.embedding_model,
        timeout_s=settings.timeout_s,
        connect_timeout_s=settings.connect_timeout_s,
    )

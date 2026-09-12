"""Registering endpoints, and finding out whether one works.

The screen a person reaches for first, because nothing else in Hera does anything until she is
pointed at a model. So it does more than store fields: it will ask the endpoint what models it
has, and it will tell you plainly why it could not.

**The key never comes back.** Every response carries ``api_key_set`` instead. A masked string
is something a person tries to edit and something a client tries to send back, and both end
with a key of asterisks saved to disk.
"""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from hera_core.config import ConfigError, HeraConfig, ModelEntry, ProviderEntry
from hera_core.config import load as load_config
from hera_core.config import save as save_config
from hera_core.deps import Container
from hera_core.schemas import (
    ActivateIn,
    ModelIn,
    ProbeOut,
    ProviderIn,
    ProviderPatch,
    ProvidersOut,
)
from hera_home import logo_path
from hera_providers import OpenAICompatibleProvider, ProviderError

router = APIRouter(tags=["providers"])


@router.get("/providers", response_model=ProvidersOut)
def list_providers() -> ProvidersOut:
    """Every endpoint she can be pointed at, and which one she is pointed at now."""
    config = _read()
    active = config.active()
    return ProvidersOut(
        providers=[entry.redacted() for entry in config.providers],
        active=active.name if active is not None else "",
    )


@router.post("/providers", response_model=ProvidersOut, status_code=status.HTTP_201_CREATED)
async def add_provider(payload: ProviderIn, container: Container) -> ProvidersOut:
    """Register an endpoint and its first model. The first endpoint registered becomes active,
    and the first model registered on it does too."""
    config = _read()
    if config.get(payload.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"there is already a provider called {payload.name!r}",
        )
    first = ModelEntry(id=payload.model_id, name=payload.model_name, options=payload.model_options)
    entry = ProviderEntry(
        name=payload.name,
        kind=payload.kind,
        base_url=payload.base_url,
        api_key=payload.api_key,
        models=[first],
        active_model=first.id,
        embedding_model=payload.embedding_model,
        timeout_s=payload.timeout_s,
        connect_timeout_s=payload.connect_timeout_s,
    )
    return await _commit(container, config.with_provider(entry))


@router.patch("/providers/{name}", response_model=ProvidersOut)
async def update_provider(name: str, payload: ProviderPatch, container: Container) -> ProvidersOut:
    """Change one endpoint's fields, kind, or logo.

    ``api_key`` left out means "leave it alone"; sent as an empty string means "clear it". Any
    other reading would make a screen that never returns the key unable to keep one.
    ``logo_data_url`` follows the same rule. Model membership is not handled here — see the
    ``/models`` routes below.
    """
    config = _read()
    existing = _require(config, name)

    changes: dict[str, Any] = payload.model_dump(
        exclude={"logo_data_url", "logo_media_type"}, exclude_none=True
    )
    entry = ProviderEntry(**{**existing.model_dump(), **changes})
    if payload.logo_data_url is not None:
        entry = _apply_logo(entry, payload.logo_data_url, payload.logo_media_type or "")
    return await _commit(container, config.with_provider(entry))


@router.post("/providers/{name}/activate", response_model=ProvidersOut)
async def activate_provider(
    name: str, container: Container, payload: ActivateIn | None = None
) -> ProvidersOut:
    """Point her at this one, immediately and without a restart.

    An optional ``model`` in the body also switches which registered model is active there in
    the same call — one action for what would otherwise be an activate followed by a second
    request.
    """
    config = _read()
    entry = _require(config, name)
    if payload and payload.model:
        try:
            entry = entry.with_active_model(payload.model)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        config = config.with_provider(entry)
    return await _commit(container, config.activated(name))


@router.delete("/providers/{name}", response_model=ProvidersOut)
async def delete_provider(name: str, container: Container) -> ProvidersOut:
    config = _read()
    _require(config, name)
    _clear_logo_file(name)
    return await _commit(container, config.without(name))


@router.get("/providers/{name}/models", response_model=ProbeOut)
async def probe_provider(name: str) -> ProbeOut:
    """Ask the endpoint what it has.

    A failure here is a normal answer, not a 500: "nothing is listening on that port" is the
    single most common thing to be wrong on a fresh install, and it deserves the reason on the
    screen you were already looking at rather than a red toast that says 500.

    Built on its own client rather than the running one, so you can check an endpoint before
    activating it — which is the whole point of being able to check. What comes back is raw
    endpoint-reported ids, not yet registered — see :func:`register_model` for turning one into
    a named model.
    """
    entry = _require(_read(), name)
    provider = OpenAICompatibleProvider(entry.settings())
    try:
        models = await provider.models()
    except ProviderError as exc:
        return ProbeOut(ok=False, models=[], error=str(exc))
    finally:
        await provider.aclose()
    return ProbeOut(ok=True, models=models, error="")


@router.post(
    "/providers/{name}/models", response_model=ProvidersOut, status_code=status.HTTP_201_CREATED
)
async def register_model(name: str, payload: ModelIn, container: Container) -> ProvidersOut:
    """Register a model against an endpoint — from a probe result or typed by hand. The first
    one registered becomes active.

    Also how a registered model is **edited**: an id that is already there is replaced rather
    than duplicated, which is what makes changing its request options this call. If it happens
    to be the active one, ``_commit`` re-points the running orchestrator at the new options and
    the next turn uses them.
    """
    config = _read()
    entry = _require(config, name)
    updated = entry.with_model(
        ModelEntry(id=payload.id, name=payload.name, options=payload.options)
    )
    return await _commit(container, config.with_provider(updated))


@router.delete("/providers/{name}/models", response_model=ProvidersOut)
async def remove_model(
    name: str, container: Container, id: str = Query(min_length=1)
) -> ProvidersOut:
    """Drop a registered model.

    ``id`` travels as a query parameter rather than a path segment: model ids routinely contain
    ``/`` (``meta-llama/Llama-3-70b`` and similar vendor-prefixed ids), which a path segment
    cannot match.
    """
    config = _read()
    entry = _require(config, name)
    if not any(m.id == id for m in entry.models):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no model called {id!r} on {name!r}"
        )
    return await _commit(container, config.with_provider(entry.without_model(id)))


@router.get("/providers/{name}/logo")
async def get_logo(name: str) -> Response:
    """The uploaded logo for a ``custom``-kind endpoint, served with its stored content type."""
    entry = _require(_read(), name)
    path = logo_path(entry.name)
    if not entry.logo_media_type or not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{name!r} has no uploaded logo"
        )
    return Response(
        content=path.read_bytes(),
        media_type=entry.logo_media_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300"},
    )


def _apply_logo(entry: ProviderEntry, data_url: str, media_type: str) -> ProviderEntry:
    """Write, replace or clear the file backing a custom logo, and reflect that in the entry."""
    _clear_logo_file(entry.name)
    if not data_url:
        return entry.model_copy(update={"logo_media_type": ""})
    raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
    path = logo_path(entry.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return entry.model_copy(update={"logo_media_type": media_type})


def _clear_logo_file(name: str) -> None:
    logo_path(name).unlink(missing_ok=True)


def _read() -> HeraConfig:
    try:
        return load_config()
    except ConfigError as exc:
        # A hand-edited file that will not parse. The parser's own complaint is the useful
        # thing to show; a default quietly taking its place would hide the typo.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _require(config: HeraConfig, name: str) -> ProviderEntry:
    entry = config.get(name)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no provider called {name!r}"
        )
    return entry


async def _commit(container: Container, config: HeraConfig) -> ProvidersOut:
    """Write the file and repoint the running application at whatever is now active."""
    save_config(config)
    active = config.active()
    if active is not None:
        await container.use_provider(
            OpenAICompatibleProvider(active.settings()),
            model=active.active_model,
            # The active model's request flags travel with its name, because they are a fact
            # about that model rather than about the endpoint -- see `use_provider`.
            options=active.active_options(),
        )
    return ProvidersOut(
        providers=[entry.redacted() for entry in config.providers],
        active=active.name if active is not None else "",
    )

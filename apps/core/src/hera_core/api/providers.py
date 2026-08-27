"""Registering endpoints, and finding out whether one works.

The screen a person reaches for first, because nothing else in Hera does anything until she is
pointed at a model. So it does more than store fields: it will ask the endpoint what models it
has, and it will tell you plainly why it could not.

**The key never comes back.** Every response carries ``api_key_set`` instead. A masked string
is something a person tries to edit and something a client tries to send back, and both end
with a key of asterisks saved to disk.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from hera_core.config import ConfigError, HeraConfig, ProviderEntry
from hera_core.config import load as load_config
from hera_core.config import save as save_config
from hera_core.deps import Container
from hera_core.schemas import ProbeOut, ProviderIn, ProviderPatch, ProvidersOut
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
    """Register an endpoint. The first one registered becomes the active one."""
    config = _read()
    if config.get(payload.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"there is already a provider called {payload.name!r}",
        )
    entry = ProviderEntry(**payload.model_dump())
    return await _commit(container, config.with_provider(entry))


@router.patch("/providers/{name}", response_model=ProvidersOut)
async def update_provider(name: str, payload: ProviderPatch, container: Container) -> ProvidersOut:
    """Change one endpoint.

    ``api_key`` left out means "leave it alone"; sent as an empty string means "clear it". Any
    other reading would make a screen that never returns the key unable to keep one.
    """
    config = _read()
    existing = _require(config, name)

    changes: dict[str, Any] = payload.model_dump(exclude_none=True)
    updated = ProviderEntry(**{**existing.model_dump(), **changes})
    return await _commit(container, config.with_provider(updated))


@router.post("/providers/{name}/activate", response_model=ProvidersOut)
async def activate_provider(name: str, container: Container) -> ProvidersOut:
    """Point her at this one, immediately and without a restart."""
    config = _read()
    _require(config, name)
    return await _commit(container, config.activated(name))


@router.delete("/providers/{name}", response_model=ProvidersOut)
async def delete_provider(name: str, container: Container) -> ProvidersOut:
    config = _read()
    _require(config, name)
    return await _commit(container, config.without(name))


@router.get("/providers/{name}/models", response_model=ProbeOut)
async def probe_provider(name: str) -> ProbeOut:
    """Ask the endpoint what it has.

    A failure here is a normal answer, not a 500: "nothing is listening on that port" is the
    single most common thing to be wrong on a fresh install, and it deserves the reason on the
    screen you were already looking at rather than a red toast that says 500.

    Built on its own client rather than the running one, so you can check an endpoint before
    activating it — which is the whole point of being able to check.
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
            OpenAICompatibleProvider(active.settings()), model=active.model
        )
    return ProvidersOut(
        providers=[entry.redacted() for entry in config.providers],
        active=active.name if active is not None else "",
    )

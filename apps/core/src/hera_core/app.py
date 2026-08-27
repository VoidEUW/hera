"""The ASGI application.

Two responsibilities beyond mounting the router: refuse a data directory from before v0.1
(ADR 7), and serve the built interface from the same origin so there is no CORS to configure
(ADR 6).

The static mount is last and catches everything, so an unknown path under ``/api`` still gets
a JSON 404 from the router rather than the interface's HTML — which would otherwise arrive at
a `fetch()` as a parse error and be blamed on the wrong layer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from hera_core import __version__
from hera_core.api import router as api_router
from hera_core.boot import LegacyHome, check_home, prepare
from hera_core.settings import CoreSettings
from hera_core.wiring import Services, build_services

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    settings: CoreSettings | None = None, *, services: Services | None = None
) -> FastAPI:
    """Build the application.

    ``services`` is the seam every test uses: pass a container wired to ``FakeProvider`` and an
    in-memory database and the whole path from HTTP to a rendered event is exercised with no
    model and no MCP servers running.
    """
    settings = settings or CoreSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = services if services is not None else build_services(settings)
        app.state.services = container
        try:
            yield
        finally:
            await container.aclose()

    if services is None:
        # Only for a real boot. A test supplying its own container has already decided where
        # its data lives, and refusing to start over the developer's own ~/.hera would be
        # absurd.
        check_home()

    app = FastAPI(
        title="Hera",
        version=__version__,
        summary="A self-hosted agentic chat space.",
        lifespan=lifespan,
        # The interface is the only client and it is served from this origin, so the
        # interactive docs are a development convenience rather than a public surface.
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.exception_handler(LegacyHome)
    async def _legacy_home(_request: Request, exc: LegacyHome) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    app.include_router(api_router, prefix=settings.api_prefix)
    _mount_interface(app, settings)
    return app


def _mount_interface(app: FastAPI, settings: CoreSettings) -> None:
    """Serve the built SvelteKit app, if it has been built.

    Absent during Python-only development and in every API test, which is why this is a
    condition rather than an assumption — a missing ``static/`` should not stop the API from
    running, it should just mean there is nothing at ``/``.
    """
    root = Path(settings.static_dir) if settings.static_dir else STATIC_DIR
    index = root / "index.html"
    if not index.is_file():
        return

    @app.get("/", include_in_schema=False)
    async def _index() -> FileResponse:
        return FileResponse(index)

    # `html=True` makes StaticFiles fall back to index.html for a path it does not have, which
    # is what a client-side router needs: /chats/<uuid> is a real URL to the browser and an
    # unknown file to the server.
    app.mount("/", StaticFiles(directory=root, html=True), name="interface")


def build_app() -> FastAPI:
    """Factory for ``uvicorn hera_core.app:build_app --factory``."""
    return create_app()


def prepare_home(settings: CoreSettings | None = None) -> None:
    """Check the data directory and make a fresh install usable. Called by the CLI."""
    settings = settings or CoreSettings()
    check_home()
    container = build_services(settings)
    prepare(container.database, container.mind, owner_id=settings.owner_id)

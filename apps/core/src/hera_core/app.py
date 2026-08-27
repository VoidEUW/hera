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
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Scope

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

    # Registered after the real routes, so they win, and before the interface mount, so the
    # mount never sees a path under /api. Without it the single-page fallback answers an
    # unknown API path with the application's HTML, which arrives at a `fetch()` as a parse
    # error and gets blamed on the wrong layer entirely.
    @app.api_route(
        "/api/{rest:path}",
        include_in_schema=False,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    )
    async def _api_not_found(rest: str) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"no such endpoint: /api/{rest}"})

    _mount_interface(app, settings)
    return app


class _Interface(StaticFiles):
    """Static files that fall back to ``index.html`` for anything they do not have.

    A single-page application needs this and ``html=True`` does not provide it: that flag only
    serves ``index.html`` for a *directory*, so ``/`` works and ``/chat/<uuid>`` — a real URL to
    the browser and an unknown file to the server — comes back 404. Every deep link and every
    reload inside a conversation lands on that path.

    Only a 404 is caught. A 405 or a permissions error is a real problem and should say so
    rather than quietly rendering the application.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def _mount_interface(app: FastAPI, settings: CoreSettings) -> None:
    """Serve the built SvelteKit app, if it has been built.

    Absent during Python-only development, which is why this is a condition rather than an
    assumption — a missing ``static/`` should not stop the API from running, it should just
    mean there is nothing at ``/``.

    Mounted last and catching everything, so an unknown path under ``/api`` still gets a JSON
    404 from the router. HTML arriving at a ``fetch()`` is a parse error blamed on the wrong
    layer.
    """
    root = Path(settings.static_dir) if settings.static_dir else STATIC_DIR
    if not (root / "index.html").is_file():
        return

    app.mount("/", _Interface(directory=root, html=True), name="interface")


def build_app() -> FastAPI:
    """Factory for ``uvicorn hera_core.app:build_app --factory``."""
    return create_app()


def prepare_home(settings: CoreSettings | None = None) -> None:
    """Check the data directory and make a fresh install usable. Called by the CLI."""
    settings = settings or CoreSettings()
    check_home()
    container = build_services(settings)
    prepare(container.database, container.mind, owner_id=settings.owner_id)

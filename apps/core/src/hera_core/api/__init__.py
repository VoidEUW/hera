"""The versioned API surface.

One router per screen rather than one per table, because that is how the interface reads it:
``system`` is the settings modal's three lists, ``profiles`` holds the mind as well because
they are one screen.

**Two groups, and the line between them is the whole of authentication** (ADR 27). The public
one is what a browser needs before anybody is signed in — the sign-in screen, the setup wizard,
a liveness probe — and everything else is behind a session. Drawing it here, once, rather than
on each route means a route added later is signed-in by default and public only on purpose.
Every unsafe request in either group passes the Origin check.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from hera_core.api import (
    account,
    artifacts,
    auth,
    chats,
    memories,
    permissions,
    profiles,
    projects,
    providers,
    servers,
    setup,
    system,
    usage,
)
from hera_core.auth import same_origin
from hera_core.deps import current_user

public = APIRouter()
public.include_router(auth.router)
public.include_router(setup.router)
public.include_router(system.public)

signed_in = APIRouter(dependencies=[Depends(current_user)])
signed_in.include_router(account.router)
signed_in.include_router(chats.router)
signed_in.include_router(artifacts.router)
signed_in.include_router(memories.router)
signed_in.include_router(permissions.router)
signed_in.include_router(projects.router)
signed_in.include_router(providers.router)
signed_in.include_router(servers.router)
signed_in.include_router(profiles.router)
signed_in.include_router(setup.instance_router)
signed_in.include_router(system.router)
signed_in.include_router(usage.router)

router = APIRouter(dependencies=[Depends(same_origin)])
router.include_router(public)
router.include_router(signed_in)

__all__ = ["router"]

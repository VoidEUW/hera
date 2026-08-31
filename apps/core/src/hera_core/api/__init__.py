"""The versioned API surface.

One router per screen rather than one per table, because that is how the interface reads it:
``system`` is the settings modal's three lists, ``profiles`` holds the mind as well because
they are one screen.
"""

from __future__ import annotations

from fastapi import APIRouter

from hera_core.api import artifacts, chats, profiles, projects, providers, system

router = APIRouter()
router.include_router(chats.router)
router.include_router(artifacts.router)
router.include_router(projects.router)
router.include_router(providers.router)
router.include_router(profiles.router)
router.include_router(system.router)

__all__ = ["router"]

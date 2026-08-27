"""Boot settings for the application, from ``HERA_*`` environment variables.

Each library reads its own (``HERA_PROVIDER_*``, ``HERA_TOOLS_*``, ``HERA_CHATS_*``,
``HERA_STORAGE_*``); this is only what the *application* decides. Keeping them apart means a
library can be lifted into another project with its configuration intact, which is the whole
premise of the workspace.
"""

from __future__ import annotations

from uuid import UUID, uuid5

from pydantic_settings import BaseSettings, SettingsConfigDict

from hera_home import database_path

OWNER_NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
"""The DNS namespace, used to derive a stable id for the single user."""

SINGLE_USER_ID = uuid5(OWNER_NAMESPACE, "hera.local")
"""Who owns everything in a single-user deployment.

Derived rather than random, so it is the same on every boot without needing a row to remember
it in. v0.1 is single-user behind a multi-user-ready seam: every route resolves an owner
through :func:`hera_core.deps.current_user` and every row carries ``owner_id``, so turning the
seam on is a login screen rather than a migration.
"""


class CoreSettings(BaseSettings):
    """What the application itself decides."""

    model_config = SettingsConfigDict(env_prefix="HERA_", extra="ignore")

    host: str = "127.0.0.1"
    """Loopback by default. Hera is self-hosted and holds a person's whole memory; binding to
    every interface is a decision someone should have to make on purpose."""

    port: int = 8756

    reload: bool = False
    """Uvicorn's auto-reload, for development."""

    owner_id: UUID = SINGLE_USER_ID

    api_prefix: str = "/api/v1"
    """Versioned from the start (ADR 6). The browser's types are generated from the OpenAPI
    schema, so an unversioned path would make every breaking change a silent one."""

    static_dir: str = ""
    """Where the built interface is. Empty means the ``static`` directory beside this package,
    which is where ``adapter-static`` writes it."""

    def database_url(self) -> str:
        """The SQLite file under ``$HERA_HOME``.

        Computed here rather than defaulted in ``hera_storage``, which is domain-free and does
        not know what ``~/.hera`` is. ``HERA_STORAGE_URL`` still overrides it — that is the
        escape hatch for pointing at PostgreSQL.
        """
        return f"sqlite:///{database_path()}"

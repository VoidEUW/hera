"""The servers she has, the tools on each, and a way to add, change and remove them (#108).

``GET /servers`` includes her own in-process server, flagged ``builtin``, because it *is* one
(ADR 4) and the screen shows it like the rest; what a person means by "my servers" is the ones
without that flag, and the composer and the health card count those. The operations live in
:mod:`hera_core.serverbook`.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Response, status

from hera_core import serverbook
from hera_core.deps import Container
from hera_core.schemas import ServerEntry, ServerOut, ServerToolOut, ToolAllowedIn
from hera_tools import InvalidToolConfig, InvalidToolName, mask

router = APIRouter(tags=["servers"])


@router.get("/servers", response_model=list[ServerOut])
async def list_servers(container: Container) -> list[ServerOut]:
    """Hera's own server first, then the ones that are running, then the ones switched off.

    A block with ``enabled: false`` is not in the registry at all -- it was never started -- so
    it is read back from the file, which is also the only place that can say it exists.
    """
    if container.registry is None:
        return []
    try:
        written = serverbook.declared(container)
    except InvalidToolConfig:
        written = {}

    rows = [
        ServerOut(
            name=state.name,
            connected=state.connected,
            tools=state.tools,
            failure=state.failure,
            builtin=state.builtin,
            kind="builtin" if state.builtin else _kind(written.get(state.name, {})),
        )
        for state in await container.registry.status()
    ]
    running = {row.name for row in rows}
    rows.extend(
        ServerOut(
            name=name,
            connected=False,
            tools=0,
            enabled=_enabled(entry),
            kind=_kind(entry),
        )
        for name, entry in sorted(written.items())
        if name not in running
    )
    return rows


@router.get("/servers/{name}/tools", response_model=list[ServerToolOut])
async def server_tools(name: str, container: Container) -> list[ServerToolOut]:
    """What a server offers, with whether she has each — the checkbox beside every tool."""
    if container.registry is None:
        raise _no_tool_layer()
    catalogue = (await container.registry.catalogue()).for_server(name)
    if not catalogue.tools and name not in {row.name for row in await list_servers(container)}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such server")
    out = []
    for tool in catalogue.tools:
        state = serverbook.tool_state(container, tool.name)
        out.append(
            ServerToolOut(
                name=tool.name,
                local_name=tool.local_name,
                description=tool.description or tool.title,
                allowed=state.allowed,
                rule=state.rule if not state.allowed else None,
                exact=state.exact,
            )
        )
    return out


@router.put("/servers/{name}/tools/{tool:path}", response_model=ServerToolOut)
async def set_tool(
    name: str, tool: str, payload: ToolAllowedIn, container: Container
) -> ServerToolOut:
    """Turn one tool on or off. Off is a `deny` rule, so it shows on the Permissions screen."""
    if container.registry is None:
        raise _no_tool_layer()
    found = (await container.registry.catalogue()).get(f"{name}__{tool}")
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such tool")
    state = serverbook.set_allowed(container, name, tool, payload.allowed)
    return ServerToolOut(
        name=found.name,
        local_name=found.local_name,
        description=found.description or found.title,
        allowed=state.allowed,
        rule=state.rule if not state.allowed else None,
        exact=state.exact,
    )


@router.get("/servers/{name}/config", response_model=ServerEntry)
async def read_config(name: str, container: Container) -> ServerEntry:
    """The entry as written, for the editor — a pasted secret comes back as `null`."""
    try:
        entry = serverbook.declared(container).get(name)
    except serverbook.NoToolLayer as cause:
        raise _no_tool_layer() from cause
    except InvalidToolConfig as cause:
        raise _bad_file(cause) from cause
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such server")
    return _entry(entry)


@router.put("/servers/{name}", response_model=ServerOut)
async def write_server(
    name: str, payload: ServerEntry, response: Response, container: Container
) -> ServerOut:
    """Add a server or replace one, then reconnect what changed. 201 for a new one."""
    try:
        created, retired = serverbook.save(container, name, _raw(payload))
    except serverbook.NoToolLayer as cause:
        raise _no_tool_layer() from cause
    except serverbook.BuiltInServer as cause:
        raise _built_in() from cause
    except (InvalidToolConfig, InvalidToolName) as cause:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(cause)) from cause
    await serverbook.close(retired)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return next(row for row in await list_servers(container) if row.name == name)


@router.delete("/servers/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(name: str, container: Container) -> Response:
    try:
        retired = serverbook.remove(container, name)
    except serverbook.NoToolLayer as cause:
        raise _no_tool_layer() from cause
    except serverbook.BuiltInServer as cause:
        raise _built_in() from cause
    except serverbook.NoSuchServer as cause:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such server") from cause
    except InvalidToolConfig as cause:
        raise _bad_file(cause) from cause
    await serverbook.close(retired)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _kind(entry: dict[str, Any]) -> Literal["stdio", "http"]:
    return "http" if entry.get("url") else "stdio"


def _enabled(entry: dict[str, Any]) -> bool:
    return entry.get("enabled", True) is not False


def _entry(raw: dict[str, Any]) -> ServerEntry:
    shown = mask(raw)
    return ServerEntry(
        kind=_kind(raw),
        command=str(shown.get("command") or ""),
        args=[str(arg) for arg in shown.get("args") or []],
        env=dict(shown.get("env") or {}),
        cwd=str(shown.get("cwd") or ""),
        url=str(shown.get("url") or ""),
        headers=dict(shown.get("headers") or {}),
        enabled=_enabled(raw),
    )


def _raw(entry: ServerEntry) -> dict[str, Any]:
    """The form as the file spells it: only what its kind uses, and `enabled` only when off."""
    written: dict[str, Any]
    if entry.kind == "http":
        written = {"url": entry.url.strip()}
        if entry.headers:
            written["headers"] = dict(entry.headers)
    else:
        written = {"command": entry.command.strip()}
        if entry.args:
            written["args"] = list(entry.args)
        if entry.env:
            written["env"] = dict(entry.env)
        if entry.cwd.strip():
            written["cwd"] = entry.cwd.strip()
    if not entry.enabled:
        written["enabled"] = False
    return written


def _built_in() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, detail="that server is part of Hera and is not in mcp.json"
    )


def _bad_file(cause: Exception) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=str(cause))


def _no_tool_layer() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail="no tools are wired in this deployment")

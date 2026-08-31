"""What she published in one conversation, for the panel beside it (ADR 13).

Three routes over a directory. There is no table, no index and no id: the filename is the
identity, ``~/.hera/chats/<chat id>/artifacts/`` is the store, and everything a card needs beyond
this travelled in the tool call that made it, which is already a persisted event.

**Two of the three deliberately do not serve HTML**, and that is the security decision this
module exists to hold. An artifact is a document a *model* wrote; serving it as ``text/html``
from Hera's own origin would put a page she generated inside the origin that holds Hera's
storage, cookies and DOM — the exact thing the sandboxed frame in the browser is there to
prevent. So the content comes back as JSON and the download comes back as an attachment with a
neutral media type, and the browser builds the frame with ``srcdoc``, where it has an opaque
origin.

The name is never turned into a path here. It goes to :mod:`hera_core.chat_files`, which is the
one place that decides a name is usable, because two implementations of that check is one too
many — see the note on ``_resolve`` there.
"""

from __future__ import annotations

from collections.abc import Awaitable
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from hera_core.chat_files import ChatFileRefused, FileArtifacts
from hera_core.deps import Db, Owner, not_found, require_chat
from hera_core.schemas import ArtifactContent, ArtifactOut

router = APIRouter(tags=["artifacts"])

DOWNLOAD_TYPE = "application/octet-stream"
"""What a download is served as, whatever the extension says.

Not ``text/html`` for a page and not ``image/svg+xml`` for a drawing, both of which a browser
renders *in this origin* if the ``Content-Disposition`` is ever weakened or ignored. The file is
saved and opened from disk, where it is somebody's own file rather than a script with a session.
"""


@router.get("/chats/{chat_id}/artifacts", response_model=list[ArtifactOut])
async def list_artifacts(chat_id: UUID, owner: Owner, db: Db) -> list[ArtifactOut]:
    """Everything published in this conversation, oldest name first.

    An empty list is a 200. A conversation that produced nothing is the ordinary state, and a 404
    would make *nothing here yet* and *no such chat* look the same to the file bar.
    """
    chat = require_chat(db, chat_id, owner)
    found = await FileArtifacts().files(str(chat.id))
    return [
        ArtifactOut(name=file.name, bytes=file.size, modified_at=file.modified_at) for file in found
    ]


@router.get("/chats/{chat_id}/artifacts/{name}", response_model=ArtifactContent)
async def read_artifact(chat_id: UUID, name: str, owner: Owner, db: Db) -> ArtifactContent:
    chat = require_chat(db, chat_id, owner)
    text = await _content(chat_id=str(chat.id), name=name)
    return ArtifactContent(name=name, bytes=len(text.encode("utf-8")), text=text)


@router.get("/chats/{chat_id}/artifacts/{name}/download")
async def download_artifact(chat_id: UUID, name: str, owner: Owner, db: Db) -> Response:
    """The file itself, as a download rather than as a page.

    Bytes rather than text, unlike the route above: everything she writes through the tool is
    text, but somebody saving a file wants the file rather than an opinion about whether it
    decodes.
    """
    chat = require_chat(db, chat_id, owner)
    body = await _guarded(FileArtifacts().raw(str(chat.id), name))
    if body is None:
        raise not_found("artifact")
    return Response(
        content=body,
        media_type=DOWNLOAD_TYPE,
        headers={
            # The filename is quoted and the name has already been through the guard, so there is
            # no separator, no newline and no NUL in it to break the header with.
            "Content-Disposition": f'attachment; filename="{name}"',
            # Belt and braces on the same decision as `DOWNLOAD_TYPE`: a browser that sniffs the
            # bytes of a page she wrote and decides to render them would undo it.
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _content(*, chat_id: str, name: str) -> str:
    """One artifact's text, or a 404."""
    text = await _guarded(FileArtifacts().read(chat_id, name))
    if text is None:
        raise not_found("artifact")
    return text


async def _guarded[T](reading: Awaitable[T]) -> T:
    """Turn the adapter's refusal into a 400.

    A refused *name* is a 400 rather than a 404, because the two are different mistakes: a client
    that asked for ``../config.toml`` should be told it asked wrongly, where a 404 reads as *try
    another path*. A file that does not decode as text lands here too, and it is the same answer
    — the request was for text and this is not any.
    """
    try:
        return await reading
    except ChatFileRefused as refused:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(refused)
        ) from refused

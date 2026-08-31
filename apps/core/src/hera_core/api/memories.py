"""What she knows about you, for the screen that shows it (ADR 16).

Five routes over a directory. There is no table and no id: ``~/.hera/memories/<key>.md`` is the
store and the filename is the identity, exactly as it is for an artifact one milestone earlier.

**This is the only place any of it is ever shown.** Every enabled memory is already in her
prompt, so nothing here exists to help *her* — it exists because a store you cannot see is a
store you cannot trust. The description and the ``why`` are never injected, which makes this
screen the only reason they are worth writing down.

**Deleting is here and nowhere else.** ``hera__forget`` switches a memory off and keeps the
file; unlinking one is a person, on this screen, and the split is the whole of *nothing a person
told her is discarded without a person present*.

The export is served as an attachment with a neutral media type, for the reason
:mod:`hera_core.api.artifacts` spells out: it is a document assembled partly from text a model
wrote, and Hera's own origin is not where that gets rendered.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from hera_core.deps import Container, Owner, not_found
from hera_core.schemas import BudgetOut, MemoryOut, MemoryPatch
from hera_memories import Memory, MemoryFull, MemoryRefused

router = APIRouter(tags=["memories"])

EXPORT_FILENAME = "MEMORY.md"
EXPORT_TYPE = "text/markdown; charset=utf-8"


@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(owner: Owner, container: Container) -> list[MemoryOut]:
    """Everything she has written down, newest first, switched-off ones included.

    Included rather than filtered, and not behind a *show disabled* toggle: the switch is about
    what a turn costs, and a list that hid what you had switched off would leave you unable to
    switch it back on.
    """
    return [_out(memory) for memory in container.memories.all()]


@router.get("/memories/budget", response_model=BudgetOut)
async def memory_budget(owner: Owner, container: Container) -> BudgetOut:
    """What the enabled memories cost, for the bar.

    Its own route rather than a field on the list, because the bar and the list are refreshed by
    different things: switching one memory changes the bar, and the list is already in hand.
    """
    budget = container.memories.budget()
    return BudgetOut(
        used=budget.used, limit=budget.limit, count=budget.count, disabled=budget.disabled
    )


@router.patch("/memories/{key}", response_model=MemoryOut)
async def update_memory(
    key: str, payload: MemoryPatch, owner: Owner, container: Container
) -> MemoryOut:
    """Edit one, or switch it on or off. A field left out is left alone.

    Both are the same route because they are the same act from the store's side and the same row
    on the screen: this is the door a *person* has to what she wrote down. Her own tools reach a
    different one — `remember` replaces a whole memory by key, and `forget` only ever switches.

    Two failures worth telling apart. Growing a memory past the ceiling, or switching one back
    on when there is no room, is a **409**: nothing about the request was wrong, the store is
    full, and the message says what is taking the space. Everything else is a 400 or a 404.
    """
    try:
        return _out(
            container.memories.update(
                key,
                text=payload.text,
                description=payload.description,
                why=payload.why,
                enabled=payload.enabled,
            )
        )
    except MemoryFull as full:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(full)) from full
    except MemoryRefused as refused:
        raise _refused(refused, key) from refused


@router.delete("/memories/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(key: str, owner: Owner, container: Container) -> None:
    """Remove the file. A person's decision and nobody else's — see the module docstring."""
    try:
        removed = container.memories.delete(key)
    except MemoryRefused as refused:
        raise _refused(refused, key) from refused
    if not removed:
        raise not_found("memory")


@router.get("/memories/export/MEMORY.md")
async def export_memories(owner: Owner, container: Container) -> Response:
    """`MEMORY.md` — every memory, verbatim, in one file you can take somewhere else.

    Lossless on purpose: what comes out can be split back into the files it came from, which is
    what makes this an export rather than a report. A summary of your memories is not something
    you can hand to another tool.
    """
    return Response(
        content=container.memories.export(),
        media_type=EXPORT_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{EXPORT_FILENAME}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


def _out(memory: Memory) -> MemoryOut:
    return MemoryOut(
        key=memory.key,
        text=memory.text,
        description=memory.description,
        why=memory.why,
        created=memory.created,
        scope=memory.scope,
        chat_id=memory.chat_id,
        source=memory.source,
        enabled=memory.enabled,
        tokens=memory.tokens,
        problems=list(memory.problems),
    )


def _refused(refused: MemoryRefused, key: str) -> HTTPException:
    """A refused *key* is a 404 when there is simply no such memory, and a 400 when the key
    could never name one — the two are different mistakes and *try another one* is only useful
    advice for the first."""
    if "no memory called" in str(refused):
        return not_found("memory")
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(refused))

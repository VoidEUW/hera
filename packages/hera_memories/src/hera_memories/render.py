"""Two renderers, and the difference between them is the point.

:func:`for_prompt` is what she reads. :func:`for_export` is what you take somewhere else. They
are not the same function because they answer different questions, and pretending otherwise
costs one of them: an export that is lean enough for a prompt has thrown away the provenance
that made it worth exporting, and a prompt that carries every field spends the budget on
metadata the model has no use for.

**What is injected is the body and the date, and nothing else.** The description is a line for
the list a person scans; ``why`` is provenance for the person and for whatever proposes changes
to memory later. Neither tells the model anything the body does not, and both would be paid for
in every turn forever — which is exactly the mistake ADR 13 caught one milestone earlier, where
a published page sat under every later question.

**The date is injected**, and it is the one piece of metadata that earns its place. It is what
lets her tell *this was true in July* from *this is true* — the age hint the retrieval design
this replaced also had, and the only part of it that survives having no retrieval.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from hera_memories.models import Memory

HEADING = "## "


def enabled_for(memories: Iterable[Memory], *, chat_id: str = "") -> list[Memory]:
    """The memories one turn carries: enabled, and either global or this conversation's.

    Sorted by key so the prompt is stable between turns. A prompt whose lines move around is a
    prompt that defeats every caching layer between here and the endpoint, for no gain — nothing
    downstream cares what order facts arrive in.
    """
    return sorted(
        (memory for memory in memories if memory.enabled and memory.belongs_to(chat_id)),
        key=lambda memory: memory.key,
    )


def for_prompt(memories: Sequence[Memory]) -> str:
    """What goes into the ``memories`` slot.

    Empty for an empty set, rather than a sentence saying there is nothing — the slot is simply
    not filled, and `hera_prompts` already drops a section with nothing in it. *You have no
    memories* is a thing to say to a person, not something to spend a turn's attention on.
    """
    blocks = []
    for memory in memories:
        when = f" ({memory.created.isoformat()})" if memory.created else ""
        blocks.append(f"{HEADING}{memory.key}{when}\n{memory.text.strip()}")
    return "\n\n".join(blocks)


def for_export(memories: Sequence[Memory], *, sources: dict[str, str] | None = None) -> str:
    """`MEMORY.md`: every memory, whole, in one file.

    **Verbatim, front matter and all**, which makes this losslessly the inverse of the store —
    what comes out can be split back into the files it came from. That is what makes it worth
    calling an export rather than a report: a summary of your memories is not something you can
    take to another tool.

    Disabled memories are included. They are still yours; the switch is about what a turn costs,
    and a backup that quietly omitted everything you had switched off would be the worst kind of
    surprise to discover from.
    """
    parts = [
        "<!-- Hera memories. One `## ` heading per memory; the heading is its key, and the "
        "block under it is the file. -->"
    ]
    for memory in memories:
        body = (sources or {}).get(memory.key)
        parts.append(f"{HEADING}{memory.key}\n\n{(body or memory.text).strip()}")
    return "\n\n".join(parts) + "\n"

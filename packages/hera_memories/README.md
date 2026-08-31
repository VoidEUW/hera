# hera-memories

What Hera remembers about you: one markdown file per memory, **all of them in the prompt**.

```python
from hera_home import memories_dir
from hera_memories import MemoryStore

store = MemoryStore(memories_dir())
store.write(
    "runs-models-locally",
    "They run local models through LM Studio on an M-series Mac. CUDA advice does not apply.",
    description="Runs local models on Apple silicon",
    why="Corrected me after I suggested CUDA flags",
)

store.recall()   # the string for hera_profiles' `memories` slot
store.budget()   # Budget(used=41, limit=4000, count=1, disabled=0)
store.export()   # MEMORY.md
```

## `~/.hera/memories/runs-models-locally.md`

```markdown
---
description: Runs local models on Apple silicon
created: 2026-08-31
scope: global
source: auto
enabled: true
why: Corrected me after I suggested CUDA flags
---

They run local models through LM Studio on an M-series Mac. CUDA advice does not apply.
```

The **filename is the key**, so writing it twice is a correction rather than a second copy of a
fact that changed. The format is `SKILL.md`'s, so a person who has edited a skill already knows
how to edit this, and a file that opens legibly in any editor is what *exportable* means.

## Why there is no retrieval

ADR 16. Ranking that silently misses is the failure that matters here: a memory that did not
arrive looks exactly like a memory that was never stored, and nothing on either side can tell
which happened. Injecting everything makes *what she knows* a property you can check by reading
the prompt.

The cost is space, so space is the feature:

- a **ceiling** in tokens, `HERA_MEMORIES_BUDGET_TOKENS`, default 4000
- **switching a memory off** keeps the file and gives the space back — the middle option between
  having something and deleting it
- a write that will not fit is **refused with the list**, so she can fold two memories into one
  rather than something being dropped for her

Only the body and the date reach the prompt. `description` is the line a person reads in a list
and `why` is provenance; neither tells the model anything the body does not, and both would be
paid for in every turn.

## What it will not do

- **List memories to the model.** They are already in its prompt.
- **Delete anything on her behalf.** `MemoryPort.forget` switches a memory off and keeps the
  file. Unlinking is a person on the settings screen, and nothing else.

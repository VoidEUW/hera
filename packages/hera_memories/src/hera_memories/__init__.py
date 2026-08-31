"""What Hera remembers about you.

One markdown file per memory under ``~/.hera/memories/``, and **every enabled one is in the
system prompt** — there is no retrieval here and that is the decision, not an omission (ADR 16).
Retrieval that silently misses is the failure that matters: a memory that did not arrive looks
exactly like a memory that was never stored, and neither the person nor the model can tell which
happened. Everything present is a property you can check by reading the prompt.

```python
from hera_memories import MemoryStore
from hera_home import memories_dir

store = MemoryStore(memories_dir())
store.write("runs-models-locally", "They run LM Studio on an M-series Mac.",
            description="Runs local models on Apple silicon")

store.recall()      # the `memories` slot for a turn
store.budget()      # Budget(used=41, limit=4000, count=1, disabled=0)
store.export()      # MEMORY.md -- every file, verbatim, in one document
```

Injecting everything is what makes the budget the feature rather than a setting: the space it
takes is bounded by nothing except what she has learned, so the ceiling is visible, a person can
switch a memory off to give the space back, and a write that will not fit is refused with what
she needs to fold two of them into one.

The format is ``SKILL.md``'s — front matter, then markdown — so a person who has edited a skill
already knows how to edit a memory, and a file that opens legibly in any editor is what
*exportable* actually means.
"""

from __future__ import annotations

from hera_memories.models import (
    CHARS_PER_TOKEN,
    KEY_PATTERN,
    MAX_DESCRIPTION,
    MAX_KEY,
    Budget,
    Memory,
    check_key,
    estimate_tokens,
)
from hera_memories.render import enabled_for, for_export, for_prompt
from hera_memories.settings import MemoriesSettings
from hera_memories.store import (
    MAX_TEXT,
    MemoryFull,
    MemoryPort,
    MemoryRefused,
    MemoryStore,
)

__all__ = [
    "CHARS_PER_TOKEN",
    "KEY_PATTERN",
    "MAX_DESCRIPTION",
    "MAX_KEY",
    "MAX_TEXT",
    "Budget",
    "MemoriesSettings",
    "Memory",
    "MemoryFull",
    "MemoryPort",
    "MemoryRefused",
    "MemoryStore",
    "check_key",
    "enabled_for",
    "estimate_tokens",
    "for_export",
    "for_prompt",
]

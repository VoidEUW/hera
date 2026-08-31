# 16. A memory is a file, and every enabled one is in the prompt

- Status: accepted
- Date: 2026-08-31

> **This reverses the plan `docs/versions/v0.2.0.md` carried for a week**, which was cosine
> ranking over a `mem_memories` table with per-tier caps. That design is not deleted — it is
> summarised at the bottom, because if the budget turns out to be the binding constraint,
> ranking is what comes back, and the per-tier-caps lesson is expensive to relearn.

## Context

Every conversation starts from nothing. `hera__remember` has been in the catalogue since v0.1 and
has answered *"memory is not available in this deployment"* every time it was called, which is the
honest version of the gap but is still the gap.

`ARCHITECTURE.md` has named `hera_memories` since the rebuild started, and the prototype earned a
real design for it: tiers, separate caps per tier, cosine over an embedding column, dedup
thresholds, hit counts. That design assumes the problem is **choosing** — that there will be more
memories than fit, so the system's job is to pick the right ones for this turn.

Two things make that assumption worth re-examining.

**The first is what a memory is *for a person*.** Everything else Hera stores is Hera-shaped: a
chat, an event list, a permission rule, a skill selection. None of it means anything outside this
application. What she knows about you is the exception — it is the part with value somewhere else,
and the part somebody would want to back up, edit by hand, or take to another tool when they stop
using Hera. A row in a SQLite table with a float vector beside it is the shape that makes that
hardest.

**The second is the failure mode of retrieval.** A memory that was stored and did not arrive looks
*exactly* like a memory that was never stored. Neither the person nor the model can tell which
happened: she says "you never told me that", the person is sure they did, and there is no way to
settle it short of reading the database. That is not a ranking bug to be tuned — it is a class of
failure that undermines the feature's whole claim, which is that she remembers.

The v0.1 design already had this shape and already knew it. The `memory_instr` mind region shipped
with the sentence *"What you were given from memory is what you happened to recall, not the whole
of what you know — never conclude that you cannot remember something."* That is an honest
instruction, and it is an instruction that exists to paper over exactly the problem above.

## Decision

**A memory is a markdown file. Every enabled one is in the system prompt. The space they take has
a ceiling, and the ceiling is visible.**

### One file per memory, and the filename is the key

```
~/.hera/memories/runs-models-locally.md
```

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

The format is `SKILL.md`'s — front matter, then markdown — which [ADR 5](0005-deterministic-skill-routing.md)
adopted from Claude Code. Adopting it again here costs nothing and buys two things: a person who has
edited a skill already knows how to edit a memory, and *exportable* means something concrete rather
than aspirational, because the file already opens legibly in any editor.

**The filename is the identity**, exactly as it is for an artifact in
[ADR 13](0013-an-artifact-is-a-file-she-publishes.md) one milestone earlier. So writing the same key
twice is a correction rather than a second copy of a fact that changed, and a memory can be named in
a tool call without an id existing anywhere.

The front matter carries what the file cannot say by being a file: `description` (the line a person
scans in a list), `why` (what made it worth writing down), `created`, `scope`, `source` and
`enabled`.

### Everything enabled is injected, whole

No ranking, no tiers, no query, no embedding. `MemoryStore.recall()` returns every enabled memory
that this conversation carries, sorted by key so the prompt is stable between turns.

What this buys is a property that can be checked rather than trusted: **what she knows is what is in
the prompt.** *She did not remember* and *she was never told* stop being indistinguishable.

**Only the body and the date are injected.** The `description` and `why` tell the model nothing the
body does not, and would be paid for in every turn forever — which is the mistake ADR 13 caught one
milestone earlier, where a published page sat under every later question. The date stays because it
is the one piece of metadata that earns its place: it is what lets her tell *this was true in July*
from *this is true*, and it is the only part of the retrieval design that survives having no
retrieval.

### So the budget is the feature, not a setting

Injecting everything means the space is bounded by nothing except what she has learned, and a prompt
that grows forever ends as a turn failing at an endpoint's context limit — which arrives as a bug
rather than as a warning. So:

- **A ceiling in tokens**, `HERA_MEMORIES_BUDGET_TOKENS`, default 4000, measured as
  `ceil(len(text) / 4)`. Deliberately an approximation: a real count needs the endpoint's own
  tokenizer, which changes when the model does, is not installed, and would make the number on
  screen depend on which model is selected. The question the bar answers — *how close am I* —
  survives being 15 % out.
- **A space-left bar on Settings → Memory.** Not a number in a corner. The bar and the refusal are
  one measurement, so they cannot disagree.
- **Switching a memory off keeps the file and gives the space back.** The middle option between
  having something and deleting it, and the reason the ceiling is livable: a memory that is true and
  rarely relevant should cost nothing and still be there. A disabled memory is listed, greyed, and
  still exported.
- **At the ceiling she is asked to merge**, and nothing is dropped for her. `remember` refuses with
  the enabled memories and what each costs, and tells her to fold two into one and switch the
  leftover off. A merge she declines, that comes back empty, or that would not free enough space
  falls back to that same refusal. **Nothing a person told her is discarded without a person
  present** is the rule underneath both.

### Two tools, and what is missing from them is the design

`hera__remember(key, text, description, why, scope)` and `hera__forget(key)`.

- **There is no tool that lists memories.** They are already in her prompt; reading them back would
  spend the context window on what is in it. The one place anything enumerates them at her is the
  refusal above, where she needs the list to act on it.
- **`forget` does not delete.** It switches a memory off and keeps the file. The word is `forget`
  because that is the word the model reaches for, so the description and the confirmation are what
  stop it meaning what the model would assume. **The only thing in the system that unlinks a memory
  is a person on the settings screen.**

`scope="chat"` learns which conversation from the call's `_meta`, never from an argument
([ADR 12](0012-a-chat-has-a-scratchpad.md)) — which is what makes it implementable at all, and it
has been waiting for that mechanism since v0.1.

### `MEMORY.md` is the export, and it is lossless

Every memory, verbatim, front matter and all, in one document — so what comes out can be split back
into the files it came from. That is what makes it an export rather than a report: a *summary* of
your memories is not something you can hand to another tool. Served as an attachment with
`nosniff`, for the reason [ADR 13](0013-an-artifact-is-a-file-she-publishes.md) gives — it is a
document partly assembled from text a model wrote, and Hera's own origin is not where that gets
rendered.

## Consequences

**The `memory_instr` mind region was wrong and is rewritten.** Its shipped default told her that
what she was given was not the whole of what she knows. Under this decision the whole of it *is*
there, and leaving that sentence in would have her hedge about facts she is looking at. The new
default says the opposite and adds the thing she now has to know: the space is shared, so a memory
has to earn its place.

**No table, no migration, no embedder.** `hera_memories` imports `hera_home` and nothing else — it
was allow-listed for `hera_storage` and now needs less than that. The `Embedder` seam that v0.1 left
open stays open for skill retrieval, where ranking is still the right shape because a skill body is
thousands of tokens and there may be hundreds of them.

**Dedup gets more important, not less.** With no retrieval to hide it, a duplicate is now something
a person sees on a screen. Normalised equality is cheap and catches most of it; whether anything
cleverer is worth it is a question for whatever proposes changes to memory later.

**The budget is over everything enabled, not over what one turn carries.** A person cannot steer by
a number that changes depending on which conversation is open, so a chat-scoped memory is charged to
the same ceiling. It over-counts slightly for any single turn, which is the direction a ceiling
should err in.

**This does not scale to thousands of memories, and it is not meant to.** At the point where a
person has more than a few dozen facts about themselves worth carrying into every conversation,
something is wrong with what is being remembered rather than with how it is stored — and the refusal
at the ceiling is what says so, at the moment it becomes true. If that turns out to be wrong, the
design below is the one to come back to.

<details>
<summary>The retrieval design this replaced</summary>

One table, `mem_memories`, carrying `kind · scope · text · chat_id · project_id · source · hits ·
negative_signals · enabled · embedding`. Cosine above a floor ranks first, then keyword overlap,
tiebroken on `hits` and then id; nothing matching at all falls back to newest-first. Each tier
filtered and capped through its **own** budget rather than one shared pool — the prototype collapsed
them once and a noisy tier immediately crowded out a deliberately small one. Injected lines carry an
age hint.

**Keyword overlap would be the default, not the degradation**, for ADR 5's reason applied harder: a
memory that stops arriving because embeddings are down looks exactly like a memory that was never
stored. An embedder that raises is treated as absent, and a turn never fails on embeddings.

**The landmine survives any design that embeds anything.** `SkillRouter.select()` is synchronous and
`hera_chats` runs it in a worker thread, so reaching the event loop from there means threading a
loop handle down, and getting it subtly wrong deadlocks a turn. The answer is to compute the query
embedding in the **async** part of the turn, before the worker-thread hop, and pass it down.

</details>

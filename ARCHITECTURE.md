# Architecture

Hera is a uv workspace. Each package has one job, owns its own tables, and imports only
downwards. The rule is mechanical: if a package needs something from a package above it, the
dependency is wrong, not the design.

```
                  apps/core  (hera-core: FastAPI + the SvelteKit app, owns migrations)
                              │
        ┌─────────────────────┼──────────────────────┐
   hera_profiles         hera_promptevo              │
   hera_tools            hera_memories        hera_skillsets
   hera_prompts *        hera_providers       hera_permissions      hera_chats
                        hera_storage *
                         hera_home
```

`*` = domain-free by contract. `hera_storage` and `hera_prompts` sit in `packages/` like the
rest, but they know nothing about Hera and never will: no table, no chat, no tool, no memory,
and no import of another `hera_*` package — not even each other. Either must be liftable into an
unrelated project unchanged. `tests/test_layering.py` gives them an empty allow-list so this is
checked, not trusted.

`hera_home` is the exception that proves the layering rule rather than a violation of it. It is
*not* domain-free — it says the word "hera" and knows the shape of `~/.hera` — but it depends on
nothing, answers one question, and sits below everything. It exists because four packages need
the same answer and two of them may not import each other; a copy of the `HERA_HOME` lookup in
each would be several places that can disagree about an environment variable name, which fails
as an empty mind directory rather than as an error.

## The packages

| Package | Owns | Never |
|---|---|---|
| `hera_home` | Where `~/.hera` is and the well-known paths inside it. Reads the environment on every call; caches nothing, creates nothing. | No I/O, no dependency, no opinion about what lives in those paths |
| `hera_storage` | The persistence foundation: engine, sessions, `Entity`/`SoftDeletable`/`Versioned` mixins, a generic `Repository`, snapshot versioning, pytest fixtures. | No table, no domain concept, no other `hera_*` import |
| `hera_prompts` | The prompt compiler: `Prompt`, `Section`, traits, renderers, budget, `fingerprint()`. Foreign content enters only as pre-rendered strings through named slots. | Does not know what a tool, memory, skill or chat is; no persistence, no I/O |
| `hera_providers` | Talking to a model. httpx streaming, the Qwen adapter, embeddings, and a `FakeProvider` for tests. Emits one normalised event union. | Knows nothing about chats, prompts or tools |
| `hera_permissions` | Whether a tool call may run: allow / deny / ask, per pattern, per profile. Pure logic. | No I/O, no registry of actual tools |
| `hera_tools` | The MCP client: server lifecycle, tool catalogue, namespacing, dispatch — plus Hera's own built-in server (`emotion`, `remember`, `note`, `skill`), which takes what it needs from above as injected **ports**. Above `ToolRegistry`, a failed call is a `ToolResult`, never an exception. | Does not decide policy, does not build prompts, does not import memories, skills or chats |
| `hera_skillsets` | `SKILL.md` packages on disk, the **router** that picks them server-side — pinned, `/slash`, retrieved — and per-owner usage counts. Bad content is a reported problem, never an exception. | Does not ask the model which skill it wants; does not write to the skills directory; does not know what a profile or a project is |
| `hera_profiles` | The mind: twelve named regions as files in a git repository, behaviour traits, profiles that select and override them, and the builder that turns the lot into a `hera_prompts.Prompt` with slots left open. Answers *who she is*; a project answers *what we are working on*. | Does not render, does not stream, does not know what fills a slot |
| `hera_chats` | **Projects**, chats, messages, the persisted event stream, and the turn orchestrator. A project is a container with behaviour — instructions, pinned skills, a default profile, and later its own files — not a folder. | Does not know which provider or which tools exist — both arrive injected; does not answer *who she is*, which is `hera_profiles` |
| `hera_memories` (v0.2) | What Hera remembers across chats: retrieval, caps, dedup, hit counts. | |
| `hera_promptevo` (v0.2) | Dreaming and experience training — the only place the words *generation*, *fitness* and *dream* are allowed. | Never writes to the mind without an accepted proposal |

## Rules that hold everywhere

**Tables.** Every package sets `__tablename__` explicitly with its own prefix (`chat_`, `mem_`,
`skill_`, `evo_`). All models share one `MetaData`, so unprefixed names from two packages would
silently collide.

**No cross-package foreign keys.** A reference to another package's entity is a bare `UUID`
column. Integrity is the application's job, not the database's. Linking tables live in
`apps/core`.

**Migrations live in `apps/core`.** Only there is every package imported, so only there does
`alembic autogenerate` see the whole schema. SQLite needs `render_as_batch=True`.

**One event union.** `hera_providers` defines the stream event types; `hera_chats` persists
them; `apps/core` serialises them to SSE; the web app reduces them into a message. A new kind of
thing the model can do is one new event variant, not a new parser.

**The server render is authoritative.** The client renders optimistically while streaming, then
replaces its view with the persisted event list at `done`. Live view and reload can therefore
never disagree.

## The turn

```
user input
  └─ hera_skillsets.SkillRouter.select()        pinned · /slash · retrieval   (no model involved)
  └─ hera_profiles.PromptBuilder.build()        mind regions → Prompt, slots bound
  └─ hera_prompts.Prompt.render()               messages + snapshot (fingerprint, dropped keys)
  └─ hera_providers.Provider.stream()           TextDelta · ThinkingDelta · ToolCallReady …
        ├─ ToolCallReady → hera_permissions.check() → hera_tools.dispatch() → results
        │                                        ↑ loops, bounded by max_iterations
        └─ TurnEnd → hera_chats persists the event list
```

## The model

The target is **Qwen3.6-35B** over an OpenAI-compatible endpoint, and the design leans on it:
native tool calling (including parallel calls), a real reasoning channel, and enough capacity
for XML-tagged prompt structure. There is deliberately **no text-based call grammar** and no
provider-specific output normalisation — both existed in the previous generation of this project
purely to compensate for a 20B model, and both cost a second parser in the frontend that had to
be kept in lockstep forever.

One thing the model is *not* trusted with: noticing that a skill is relevant. That selection is
code, in `hera_skillsets`.

## Data on disk

```
~/.hera/                 HERA_HOME overrides
  hera.sqlite3           everything relational
  mind/                  a real git repository, one file per mind region
  skills/<name>/SKILL.md skill packages, syncable from a git repo
  mcp.json               Claude-Desktop-compatible `mcpServers` shape
  config.toml            boot settings
```

Boot refuses to start against a pre-v0.1 `~/.hera/` (it looks for `hera.db` and `*_legacy_v0*`
tables) and tells you to move it aside. Nothing is ever deleted for you.

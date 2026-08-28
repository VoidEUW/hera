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
                        hera_storage *          hera_mcp
                         hera_home
```

`*` = domain-free by contract. `hera_storage` and `hera_prompts` sit in `packages/` like the
rest, but they know nothing about Hera and never will: no table, no chat, no tool, no memory,
and no import of another `hera_*` package — not even each other. Either must be liftable into an
unrelated project unchanged. `tests/test_layering.py` gives them an empty allow-list so this is
checked, not trusted.

`hera_mcp` has an empty allow-list too, for a different reason: it is *entirely* about Hera —
her own tools, the vocabulary of `emotion`, the sentence a model reads before calling
`remember` — but what it needs from the rest of the system arrives as a port, so it imports
nothing of ours. It is the server she **is**; `hera_tools` is the client she **has**, and the
client does not know it exists. The application mounts one into the other.

`hera_home` is the exception that proves the layering rule rather than a violation of it. It is
*not* domain-free — it says the word "hera" and knows the shape of `~/.hera` — but it depends on
nothing, answers one question, and sits below everything. It exists because four packages need
the same answer and two of them may not import each other; a copy of the `HERA_HOME` lookup in
each would be several places that can disagree about an environment variable name, which fails
as an empty mind directory rather than as an error.

## The packages

| Package | Owns | Never |
|---|---|---|
| `hera_home` | Where `~/.hera` is and the well-known paths inside it. Reads the environment on every call; caches nothing, creates nothing. `chat_dir()` is the one that refuses its argument — a chat id arrives from a tool call, and `..` there would put a scratchpad in the mind repository | No I/O, no dependency, no opinion about what lives in those paths |
| `hera_storage` | The persistence foundation: engine, sessions, `Entity`/`SoftDeletable`/`Versioned` mixins, a generic `Repository`, snapshot versioning, pytest fixtures. | No table, no domain concept, no other `hera_*` import |
| `hera_prompts` | The prompt compiler: `Prompt`, `Section`, traits, renderers, budget, `fingerprint()`. Foreign content enters only as pre-rendered strings through named slots. | Does not know what a tool, memory, skill or chat is; no persistence, no I/O |
| `hera_providers` | Talking to a model. httpx streaming, the Qwen adapter, embeddings, and a `FakeProvider` for tests. Emits one normalised event union. | Knows nothing about chats, prompts or tools |
| `hera_permissions` | Whether a tool call may run: allow / deny / ask, per pattern, per profile. Pure logic. | No I/O, no registry of actual tools |
| `hera_mcp` | The MCP server Hera **is**: `emotion`, `remember`, `note`, `skill` on a real `MCPServer`, the **ports** the three that touch the rest of the system take, and the stance vocabulary `hera__emotion` draws on. The tool descriptions are prompt text — changing them changes her behaviour. | Imports no other `hera_*` package. Does no I/O: where the person's own vocabulary is stored is `hera_core.emotions` |
| `hera_tools` | The MCP **client**: server lifecycle, tool catalogue, namespacing, dispatch. Mounts whatever in-process server it is handed, under that server's own name. Above `ToolRegistry`, a failed call is a `ToolResult`, never an exception. | Does not decide policy, does not build prompts, does not import memories, skills or chats — and does not know `hera_mcp` exists |
| `hera_skillsets` | `SKILL.md` packages on disk, the **router** that picks them server-side — pinned, `/slash`, retrieved — and per-owner usage counts. Bad content is a reported problem, never an exception. | Does not ask the model which skill it wants; does not write to the skills directory; does not know what a profile or a project is |
| `hera_profiles` | The mind: twelve named regions as files in a git repository, behaviour traits, profiles that select and override them, and the builder that turns the lot into a `hera_prompts.Prompt` with slots left open. Answers *who she is*; a project answers *what we are working on*. | Does not render, does not stream, does not know what fills a slot |
| `hera_chats` | **Projects**, chats, messages, the persisted `ChatEvent` stream (ADR 10), and the turn orchestrator. A project is a container with behaviour — instructions, pinned skills, a default profile, and later its own files — not a folder. | Does not know which provider or which tools exist — both arrive injected; does not answer *who she is*, which is `hera_profiles`; raises nothing — a turn closes with a reason |
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

**One event union per boundary, with a total mapping between them.** `hera_providers` defines
what a *model* can emit. `hera_chats.ChatEvent` wraps it and adds what a *turn* contains — a
skill selection, a tool result, a permission request — because none of those is model output and
the model boundary must not learn what a skill is. See
[ADR 10](docs/adr/0010-chat-events-wrap-the-provider-union.md). `apps/core` serialises
`ChatEvent` to SSE and the web app reduces it into a message. A new kind of thing the model can
do is one variant in `hera_providers` plus one line of mapping; a new kind of thing a turn
contains is one variant in `hera_chats` and no change below. Neither is ever a parser.

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
        ├─ ToolCallReady → hera_permissions.check() → hera_tools.dispatch() → ToolResultEvent
        │                    └─ ask → PermissionRequired, turn closes, resumable
        │                                        ↑ loops, bounded by max_iterations
        └─ TurnEnd consumed per round trip → one TurnClosed ends the turn
             └─ hera_chats persists the coalesced ChatEvent list
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
  chats/<id>/scratch/    her working files for one conversation; gone when the chat is
  mcp.json               Claude-Desktop-compatible `mcpServers` shape
  config.toml            registered endpoints, written by the interface
  trusted.json           skill ids and the SHA-256 you accepted; optional
  emotions.json          her stance vocabulary, once it has been changed; optional
```

`trusted.json` is what a **verified** mark on the Skills screen means, and it is the only thing
that can mean it: a skill that declared its own trustworthiness would have declared nothing.
`hera_skillsets` digests each `SKILL.md` because it is already holding the bytes; `apps/core`
decides what the digest means, because one file covers both skills and — later — MCP servers,
and neither of those packages may import the other. A listed id whose digest no longer matches
reads as **changed**, which is a different sentence from *never verified* and the one worth
saying out loud.

`config.toml` holds the model providers — several may be registered, one is active. Each library
still reads its own `HERA_*` environment variables and the file is **seeded from them** the
first time it is written, so an existing `HERA_PROVIDER_BASE_URL` is what you find already
filled in on the Models screen. After that the file wins: a setting you can change on screen and
that quietly does not apply is worse than one that overrides a variable.

Boot refuses to start against a pre-v0.1 `~/.hera/` (it looks for `hera.db` and `*_legacy_v0*`
tables) and tells you to move it aside. Nothing is ever deleted for you.

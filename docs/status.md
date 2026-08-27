# Status

Where the rebuild stands and what is settled, so a new session can pick up without re-reading
the history. Updated as milestones land — this file is a snapshot, not a changelog.

**Last updated:** 2026-08-27 · **Version:** v0.1, the spine runs · **Strategy:** thin spine first, then deepen

---

## The short version

Hera is being rebuilt from an empty repository. The previous version — one FastAPI application
with Jinja and HTMX, a German interface, a hand-written tool registry and a text call grammar
around GPT-OSS-20B — is retired to [prototype.md](prototype.md) and is wrong about everything
structural.

The replacement is a **uv-workspace monorepo**: small libraries under `packages/`, and one
application, `hera-core` at `apps/core/` — a FastAPI JSON/SSE API with the SvelteKit interface
under `web/`, built into the directory the API serves. Tools come from **MCP servers**, know-how
from **`SKILL.md` skills**, and the target model is **Qwen3.6-35B** exclusively.

## Settled decisions

Each has a record in [adr/](adr/); read those before reopening one.

| | Decision | Why it matters day to day |
|---|---|---|
| [1](adr/0001-uv-workspace-monorepo.md) | One uv-workspace monorepo | `hera_storage` and `hera_prompts` moved in from their own repositories but keep a **domain-free contract**: no table, no chat, no `hera_*` import. Packages stay independently consumable — see *Reuse* below |
| [2](adr/0002-qwen-only-target-model.md) | Qwen3.6-35B is the only target | No harmony normalisation, no text call grammar, no second parser in the browser, no positional-argument fallback. XML prompt format, native tool calling |
| [3](adr/0003-emotions-as-tool-calls.md) | Emotions are tool calls | `hera__emotion(kind, text)`, `kind` is free text, unknown kinds render generically. Parallel calls mean a whole turn's emotions cost one round-trip |
| [4](adr/0004-mcp-as-the-tool-layer.md) | MCP is the tool layer | `~/.hera/mcp.json` in Claude-Desktop shape. Hera's own tools are an in-process MCP server, not a special case |
| [5](adr/0005-deterministic-skill-routing.md) | Skills are selected by code | The target model does not reliably notice a skill applies. Pinned → `/slash` → retrieval, all server-side, before the model sees the turn |
| [6](adr/0006-spa-over-json-sse-api.md) | SvelteKit over a JSON/SSE API | API renders no HTML; client types are generated from OpenAPI; server render stays authoritative at `done` |
| [7](adr/0007-fresh-start-no-legacy-import.md) | Empty `~/.hera/` | No importer. Boot refuses to run against a pre-v0.1 directory and tells you to move it aside; nothing is deleted |
| [8](adr/0008-github-flow-and-required-checks.md) | GitHub Flow, protected `main` | PR for everything, squash merge, linear history, required checks, zero required approvals (single maintainer) |
| [9](adr/0009-one-application-package.md) | One application package, `hera-core` | `apps/core/` holds the API and the web app; `packages/` stays libraries only, so the layering guard keeps meaning what it means |
| [10](adr/0010-chat-events-wrap-the-provider-union.md) | `ChatEvent` wraps `hera_providers.Event` | A skill selection, a tool result and a permission request are not model output. Two unions, one total mapping, still no parser — and `hera_providers` keeps its empty allow-list |

Other constraints that are decided but did not need a record: English everywhere with an i18n
seam; single-user login in v0.1 behind a multi-user-ready seam (`Depends(current_user)` on every
route, `owner_id` on every row); desktop-shaped interface, installable as a PWA on the phone.

## What exists

```
pyproject.toml            uv workspace root — ruff, mypy --strict, pytest, coverage, all shared
packages/hera_home/       where ~/.hera is; no dependencies, no I/O
packages/hera_storage/    vendored, unchanged in behaviour
packages/hera_prompts/    vendored, unchanged in behaviour
packages/hera_providers/  the model boundary: event union, Qwen adapter, transport, FakeProvider
packages/hera_permissions/ allow · deny · ask, resolved by pattern and profile
packages/hera_tools/      the MCP client, the namespaced catalogue, and her own server
packages/hera_profiles/   the git-backed mind, behaviour traits, profiles, the PromptBuilder
packages/hera_skillsets/  SKILL.md packages, the router, usage counts
packages/hera_chats/      projects, chats, the persisted event stream, the turn orchestrator
apps/core/                hera-core: the FastAPI JSON/SSE API, alembic, the CLI
apps/core/web/            the SvelteKit interface, built into the directory the API serves
tests/                    repository-level guards (see below)
tests/e2e/                Playwright against the real application and FakeProvider
.github/                  CI, CodeQL, release, templates, CODEOWNERS, dependabot
docs/adr/                 nine decision records
```

**The foundation and capability layers are on `main`.** `hera_tools` merged as #6/#8 — 450
tests, 99 % coverage. `FakeProvider` means every layer built on top is testable without a model
running. The whole suite is 571 tests at 99 % coverage.

**The whole of v0.1 exists and the spine runs**, on four stacked branches off `main`:
`feat/hera-profiles`, `feat/hera-skillsets`, `feat/hera-chats`, `feat/hera-core`. A message
typed into the browser reaches the model boundary through the router, the mind and the turn
orchestrator, and comes back as Server-Sent Events the interface renders — verified in a real
Chromium against `FakeProvider`, including that a reload shows exactly what was streamed.

838 tests at 99 % coverage, plus 18 vitest and 3 Playwright. Profiles brought `hera_home` with
them: `HERA_HOME` had been resolved by `hera_tools.settings.hera_home()` with a note saying to
lift it when a second package needed it, and the mind directory was that second package.

Two things worth knowing before building on the foundation:

- **The event union is the contract.** `hera_providers.events` defines what a model can emit.
  A new kind of thing the model can do is one new variant there, persisted by `hera_chats`,
  serialised by `apps/core`, rendered by its web app — never a new parser. `EVENT_ADAPTER`
  round-trips a single event, so persistence goes through the union rather than through each
  variant.
- **A malformed tool call is not an error.** Unparseable arguments arrive as
  `ToolCallReady.parse_error` rather than as an exception, so one bad call does not discard the
  calls that arrived beside it and the turn stays alive. Feed it back as a tool result and let
  the model correct itself. Actual failures — unreachable endpoint, timeout, bad status, a
  connection that breaks mid-answer — raise a `ProviderError`; nothing from httpx escapes. The
  layer owning the turn catches them, because it is the only one that knows how much of the
  answer already arrived. `StreamInterrupted` is the one to special-case: persist the partial
  events and close the list with a `cancelled` turn.

### What `hera_tools` settled

- **Above `ToolRegistry`, nothing raises.** Denied, misnamed, unreachable, timed out, or a tool
  that failed on purpose — all of them are a `ToolResult` with `ok=False` and a `text` written
  for the model to read and correct itself with. `ManagedServer` below it still raises, so it
  is honest used on its own. A turn therefore needs no `try` around a tool call.
- **Her own tools are a real MCP server**, reached in-process by the same client every other
  server is reached by. `emotion`, `remember`, `note`, `skill` under `hera__*`. The three that
  touch the rest of the system take **ports** (`hera_tools.ports`), because this package may
  not import memories, skills or chats — the application wires them, and what is unwired
  answers "not available in this deployment" rather than vanishing from the catalogue.
- **The SDK is `mcp` 2.x**, whose `Client` accepts a URL, `StdioServerParameters`, a transport,
  or a `Server` object for the in-process case. Note `httpx2`, not `httpx`: the MCP SDK ships
  its own HTTP client library, and that is how request headers reach a remote server.
- **A client is owned by one worker task.** anyio task groups are task-affine, so a client
  opened in a request and closed at shutdown unwinds into "cancel scope in a different task".
  Every server therefore has a worker task that holds its client for the connection's whole
  life; calls are queued to it and run as its children, which keeps parallel calls parallel.
- **A dead stdio server does not look dead.** When the subprocess exits, the SDK's client keeps
  reporting healthy and every later call fails with `MCPError("Connection closed")` forever.
  That is detected explicitly and the connection retired, so the next call starts a fresh
  process. Without it, one crash is a dead tool until Hera restarts.
- `~/.hera/mcp.json` is read in the Claude-Desktop shape with `${VAR}` expansion; an unset
  variable is an error, because a blank credential fails later and somewhere else. `HERA_HOME`
  now comes from `hera_home.home()`; `hera_tools.settings.CONFIG_FILENAME` is an alias kept so
  nothing here has to say "MCP" twice.

### What `hera_profiles` settled

- **Twelve regions, not fifteen.** `grammar` is gone: it described the EMOTION/NOTE/TRACE/CALL
  text format that ADR 2 deleted, and shipping it would invite the model to use a call syntax
  nothing parses. `mem_overview` folded into `memory_instr`, and `mem_ex` waits for
  `hera_memories`, where it is a collection rather than a region.
- **Two doors, not one door and a filter.** `MindRepository.write()` is the person's and opens
  every region including `safety` — that is the actual mechanism behind "add a rule without
  touching code". `propose()` is everything else's and raises `RegionLocked` on an owner-fixed
  region. `hera_promptevo` will only ever call the second, so a bug in a proposer cannot become
  a bug in her conduct.
- **`git` the binary, not a binding.** Init, add, commit, log, show. Every invocation pins
  `user.name`/`user.email` and sets `commit.gpgsign=false`, so a machine where git was never
  configured is not a special case. Provenance rides in a `Hera-Origin` trailer, which
  `git log --format` can read without parsing prose.
- **A profile owns no text.** It disables regions, overrides individual ones, sets traits, and
  pins skills *by name* — bare strings, because this package sits below `hera_skillsets`.
- **`sqlalchemy.ext.mutable` does not work under SQLModel.** SQLModel's `__setattr__` calls
  SQLAlchemy's `set_attribute` and then writes the raw value into the model's `__dict__`, so
  the coerced `MutableDict` is overwritten the moment it is made. `ProfileRepository.save()`
  flags the four JSON columns by name instead, and named setters cover the common edits. An
  in-place edit followed by a bare `session.flush()` is silently lost — there is a test that
  says so, so the trap is documented rather than hidden.
- **Everything is synchronous**, like `hera_storage`. The turn orchestrator runs it in a
  worker thread. An async facade over `subprocess` would be a thread pool wearing a costume.

### What `hera_skillsets` settled

- **Retrieval works with no model endpoint.** ADR 5 names keyword overlap as the fallback, and
  it is what runs by default rather than something waiting for v0.2 — a skill that silently
  stops arriving because embeddings are down looks exactly like a skill that was not relevant.
  Terms are weighted by how few skills contain them, and a skill is scored on how much of *its
  own* description the turn covered; scoring the turn's coverage would reward whichever
  description was longest. An `Embedder` port improves it; an embedder that raises is treated
  as one that is absent.
- **The directory name is the skill's identifier**, not the frontmatter `name`. A disagreement
  is a reported problem, not an override — two sources of truth for an identifier is how a
  skill becomes unreachable under the name it appears with.
- **`description: Use when: …` is invalid YAML** and PyYAML rejects the whole block over it,
  which would silently cost the skill its description and make it unretrievable. Frontmatter
  that fails to parse is re-read line by line and the rescue is reported, so the author is told
  to quote the value instead of wondering why retrieval never fires.
- **Nothing raises for bad content.** Unparseable YAML, no description, an empty body — the
  skill still loads carrying `problems` written for a person. A directory with no `SKILL.md`
  becomes a `BrokenSkill` in `Catalogue.broken` rather than being skipped.
- **`missing` and `dropped` are different fields.** One is a pin whose folder is gone, the
  other is a skill that exists and did not fit the budget. Same-looking absence, opposite fixes.

### `hera_prompts` grew one field

`Section.escape`, defaulting to `True`, which is the behaviour it always had. The XML renderer
escapes `&`, `<` and `>` in section text — correct for content this project authors, and wrong
for a slot. A skill body reached the model as `if count &lt; limit &amp;&amp; ready`, so the
model was reading a corrupted sample of the very thing the section existed to teach it.
`hera_profiles` sets `escape=False` on every slot section and `True` on every region. The
exposure is a slot that could appear to close its own element early, which matters far less
here than in a browser: nothing parses this output, and the content came from a file its owner
wrote.

### What `hera_chats` settled

- **`ChatEvent` wraps the provider union** rather than extending it — [ADR 10](adr/0010-chat-events-wrap-the-provider-union.md).
  Growing `hera_providers.Event` with `tool_result` would have made the model boundary carry a
  concept from `hera_tools`, and that package's empty allow-list is what lets it stand alone.
- **`TurnEnd` never reaches the browser.** It is the model's full stop for one round trip and a
  turn with tools has several; the orchestrator consumes them and closes the turn once with
  `turn_closed`, whose reason set is wider — a turn can also be waiting for a person.
- **An `ask` closes the turn instead of blocking it.** `awaiting_permission`, events persisted,
  and answering the card starts a new turn that *resumes the same message* through
  `TurnContext.resume`. A turn holding an SSE response open waiting for a person dies with the
  tab. A resumed turn does not re-route skills and does not re-stream what the client already
  has.
- **Nothing raises into the caller's loop**, and there is no error module at all. A dead
  provider, a broken stream, a runaway tool loop: each closes the turn with a reason.
  `Turn.recorded` is correct at every moment, so a cancelled turn keeps the text that arrived.
- **History is rebuilt from the event list, not from a column.** One assistant turn becomes
  several wire messages — assistant-with-calls, one `tool` message per result, assistant again.
  Flattening loses the `tool_call_id` pairing and the model ignores the result *silently*. A
  call with no result still gets a message saying it never ran.
- **Text is coalesced before storage.** Hundreds of `text_delta` events become one; the variant
  is unchanged, so live view and reload still render the same thing.
- **`Tools` is a narrowing port, not an inverting one.** `hera_chats` may import `hera_tools`
  and does; the protocol says which three methods a turn actually uses, and lets a test drive
  the loop without MCP servers.

### What `apps/core` settled

- **The streaming route commits before it streams.** A `Depends`-provided session commits at
  teardown, which for a `StreamingResponse` is *after the last byte* — so the recording session
  opened at the end of the stream found no assistant row and persisted the whole turn into the
  void. The answer streamed perfectly and was gone on reload. The route now commits and
  `expunge_all()`s deliberately: the first so another session can see the rows, the second
  because `commit()` expires every instance and the turn reads the profile and project from a
  worker thread.
- **In-memory SQLite hid it.** `Database.in_memory()` uses a `StaticPool` — one connection
  shared by every session — so a second session sees the first's *uncommitted* rows. The API
  tests now use a file per test, which is the only way they can tell that class of bug apart
  from correctness. Thirteen of them fail if the commit is removed.
- **A single-page fallback is not `html=True`.** That flag serves `index.html` for a
  *directory*; `/chat/<uuid>` — every deep link and every reload inside a conversation — comes
  back 404. `_Interface` catches the 404 and serves the index, and a catch-all under `/api`
  is registered *before* the mount so an unknown endpoint still answers JSON.
- **Her own tools are allowed by default.** `Policy(fallback=ASK)` means every tool asks,
  including `hera__emotion`, which ADR 3 makes the everyday case — a confirmation card several
  times a turn teaches a person to click through cards without reading them, which is the
  failure that actually matters. `DEFAULT_POLICY` allows `hera__*` and asks for the rest.
- **Embeddings are deliberately unwired.** `SkillRouter.select()` is synchronous and
  `hera_chats` runs it in a worker thread, so reaching the event loop from there means
  threading the loop handle down to the embedder, and getting it subtly wrong deadlocks a turn.
  ADR 5's keyword fallback is what runs. The cost is worse ranking, not a missing feature, and
  `Embedder` is the seam it lands on in v0.2.

### What the interface settled

- **One reducer, two callers.** `turn.ts` runs on the live stream and on the persisted list, so
  "the server render is authoritative" is a property rather than an intention — there is a test
  asserting a coalesced list and a streamed one reduce to the same thing.
- **The only parser in the browser is the SSE transport.** `EventSource` cannot POST, so the
  response body is split on the protocol's own frame boundary. What comes out is JSON the
  server already discriminated; nothing parses model output.
- **An unknown variant renders as a row saying so.** An interface that drops what it does not
  recognise makes a missing feature and a broken one look identical.
- **Two reactive loops cost an afternoon.** `effect_update_depth_exceeded` stops Svelte
  rendering the page at all, with nothing on screen to say why. Both causes are worth
  remembering: assigning `scrollTop` inside an `$effect` that also reads the `$state` its own
  scroll handler writes, and calling an initialiser from an `$effect` when the initialiser both
  reads and writes the same state. One-time setup goes at the top of the component; `ssr =
  false` means it only ever runs in the browser anyway.
- **An emotion is drawn once.** Its `tool_call_ready` renders as a card inline; the matching
  `tool_result` would otherwise fall through to a gutter row and draw the same thing twice. A
  *failed* emotion keeps its row — one she showed and the system refused is exactly what
  openness means you get to see.

### The guards

Rules that would otherwise rot are tests, not prose:

| Test | Fails when |
|---|---|
| `test_layering.py` | a package imports sideways or upwards, or reaches into `apps/`. Each package has an explicit allow-list; `hera_storage` and `hera_prompts` have an empty one |
| `test_workspace.py` | a member is missing from mypy's `files`, from coverage's `source`, or from the root `[tool.uv.sources]`; or two test modules would shadow each other. `conftest.py` is exempt because pytest loads it by path — mypy does not, which is why `[tool.mypy] exclude` drops it |
| `test_docs.py` | a decision record is unindexed, misnumbered, or has no status |

### CI

`lint` (ruff + every pre-commit hook) · `types` (mypy --strict) · `test` (3.12 and 3.13, 90 %
coverage gate) · `web` (prettier, eslint, svelte-check, vitest, build) · `e2e` (Playwright
against the real application) · `analyze` (CodeQL, `python` and `actions`). The `web` and `e2e`
guards now find what they were waiting for, so both do real work.

**Known open:** CodeQL's `actions` queries report `actions/missing-workflow-permissions` five
times against `ci.yml`, which declares no `permissions:` block and so runs every job with the
default `GITHUB_TOKEN` scope. `release.yml` and `codeql.yml` both declare one. Medium severity,
below the ruleset threshold, so it blocks nothing — the fix is `permissions: contents: read` at
the top of `ci.yml`.

### Merging into `main`

`main` is guarded by the **`protect-main` ruleset**, not classic branch protection — the classic
API answers *"Branch not protected"*, which is misleading. Read it with
`gh api repos/VoidEUW/hera/rulesets`. It requires linear history, squash merge only, resolved
review threads, and a **CodeQL result**. `require_code_owner_review` is off, because the sole
`CODEOWNERS` entry is the only maintainer and nobody can approve their own pull request — ADR 8
already describes the intent as zero required approvals.

Three consequences, each of which has already cost a blocked merge:

- **`.github/workflows/codeql.yml` has to keep existing.** The ruleset waits for a CodeQL
  result; with no workflow nothing produces one, and every pull request blocks indefinitely on
  *"Waiting for Code Scanning results"*. Advanced setup rather than GitHub's default setup, so
  the configuration is reviewable in a pull request instead of living only in settings.
- **Leave the CodeQL query suite at the default.** `security-and-quality` was tried; every
  finding it added was a false positive — `assert` after `raise` inside `with pytest.raises(...)`
  read as unreachable, SQLAlchemy's `@declared_attr.directive def __table_args__(cls)` read as
  needing `self`, an import kept for its side effect read as unused. ruff and mypy already hold
  that bar and understand the idioms. Because unresolved review threads block the merge, a noisy
  query is not merely noise here — it is a stop.
- **`mergeStateStatus: CLEAN` means no conflicts, not a correct diff.** After a squash merge, a
  branch built on the pre-squash tip still reports clean while proposing to *undo* whatever
  exists only in the squash. Check `git diff --name-status origin/main HEAD` for deletions
  before merging, and rebase with `git rebase --onto origin/main <old-base>` so only your own
  commits replay.

GitHub refuses `gh pr merge` for anything it considers part of a stack. Use
`PUT /repos/{owner}/{repo}/pulls/{n}/merge-async` with `sha=` pinning the head you verified.

## Releases and deployment

**Tags are the moving point.** Nothing ships off a branch; a tag produces a release, and a
release is what gets deployed.

| Tag | Releases |
|---|---|
| `v1.2.3` | the application |
| `hera-skillsets-v0.1.0` | one package, wheel attached |

`release.yml` rejects a package tag whose version disagrees with that package's
`pyproject.toml`.

## Reuse from another project

A monorepo normally costs this; here it does not. Another project — `hera-code`, say — depends
on one package by naming its subdirectory:

```toml
[project]
dependencies = ["hera-skillsets"]

[tool.uv.sources]
hera-skillsets = { git = "https://github.com/VoidEUW/hera", subdirectory = "packages/hera_skillsets", tag = "hera-skillsets-v0.1.0" }
```

uv resolves that package's own `hera_*` dependencies from the **same commit and subdirectory**,
so the consumer declares one line and gets a consistent set. The prerequisite is in this
repository: every member another member depends on needs `{ workspace = true }` in the root
`[tool.uv.sources]`, which `test_workspace.py` enforces.

Skills are not Python packages — a `SKILL.md` directory is content, synced into `~/.hera/skills/`
or pointed at directly by Claude Code. They live in the separate `hera-skills` repository.

## What comes next

**v0.1 is spine-complete.** ~~`hera_tools`~~ → ~~`hera_profiles`~~ → ~~`hera_skillsets`~~ →
~~`hera_chats`~~ → ~~`apps/core`~~ → ~~the end-to-end suite~~. Every package exists and the
whole path runs.

**Now the deepening pass**, which is what the thin-spine strategy was for. In rough order:

1. **React to the build.** `docs/frontend.md` says the design language gets adjusted once there
   is something to argue with. There is now: run `uv run hera serve` and argue with it. Open
   questions it can now answer — the display face, whether the ocellus lands, where thinking
   lives, the exact palette.
2. **Her identity.** The twelve mind regions ship with placeholder text that says what belongs
   in each. Writing them is what makes her Hera, and it is a text editor in Settings → Mind,
   not code.
3. **A real endpoint.** Everything so far runs against `FakeProvider`. Point
   `HERA_PROVIDER_BASE_URL` at the local server and find out what Qwen3.6-35B actually does
   with the prompt — the `xml` layout, the tool catalogue, the emotion vocabulary.
4. **The gaps left on purpose.** The command palette behind `⌘K` (it opens Settings for now),
   the mobile sheet, project instructions in the interface, and the embedder seam.

**v0.2 — what makes her Hera.** `hera_memories` (embeddings, retrieval, caps, dedup, hits),
trace compaction and the context meter, `hera_promptevo` (dreaming and experience training).
Retrieval and the embedder land together, which is why the seam is left rather than filled.

**The application is one package now.** `hera-core` at `apps/core/` holds the API and, under
`web/`, the SvelteKit interface — not two directories under `apps/`. See
[ADR 9](adr/0009-one-application-package.md), which supersedes the layout clause of ADR 1 and
ADR 6 and leaves everything else in both standing. It stays out of `packages/` on purpose: that
directory means *a library another project can consume*, and `tests/test_layering.py` scans it
and demands an allow-list per member. The application is the one thing that legitimately imports
everything.

**v0.3 — reach.** Hera as an MCP server so Claude Code can read her memory and skills, scheduled
dreaming, agent personas branching the mind repository, a coding agent profile.

## Working on this

`CLAUDE.md` is the map, `ARCHITECTURE.md` the layering, `CONTRIBUTING.md` the setup and the
loop. `uv sync --all-packages`, then `uv run pre-commit install` — the hooks run ruff, mypy and
the conventional-commit check, and CI runs the same hooks so the configuration cannot drift.

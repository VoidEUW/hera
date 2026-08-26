# Status

Where the rebuild stands and what is settled, so a new session can pick up without re-reading
the history. Updated as milestones land — this file is a snapshot, not a changelog.

**Last updated:** 2026-08-27 · **Version:** v0.1 in progress

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

Other constraints that are decided but did not need a record: English everywhere with an i18n
seam; single-user login in v0.1 behind a multi-user-ready seam (`Depends(current_user)` on every
route, `owner_id` on every row); desktop-shaped interface, installable as a PWA on the phone.

## What exists

```
pyproject.toml            uv workspace root — ruff, mypy --strict, pytest, coverage, all shared
packages/hera_storage/    vendored, unchanged in behaviour
packages/hera_prompts/    vendored, unchanged in behaviour
packages/hera_providers/  the model boundary: event union, Qwen adapter, transport, FakeProvider
packages/hera_permissions/ allow · deny · ask, resolved by pattern and profile
packages/hera_tools/      the MCP client, the namespaced catalogue, and her own server
tests/                    repository-level guards (see below)
.github/                  CI, CodeQL, release, templates, CODEOWNERS, dependabot
docs/adr/                 nine decision records
```

**The foundation layer is complete and merged.** All four packages that import no other `hera_*`
package are on `main`. `FakeProvider` means every layer built on top of them is testable without
a model running.

**`hera_tools` is built** and sits on the branch `feat/hera-tools`, not yet merged. 450 tests,
99 % coverage.

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
  is resolved by `hera_tools.settings.hera_home()` — the first package that needed it. Lift it
  when a second one does.

### The guards

Rules that would otherwise rot are tests, not prose:

| Test | Fails when |
|---|---|
| `test_layering.py` | a package imports sideways or upwards, or reaches into `apps/`. Each package has an explicit allow-list; `hera_storage` and `hera_prompts` have an empty one |
| `test_workspace.py` | a member is missing from mypy's `files`, from coverage's `source`, or from the root `[tool.uv.sources]`; or two test modules would shadow each other. `conftest.py` is exempt because pytest loads it by path — mypy does not, which is why `[tool.mypy] exclude` drops it |
| `test_docs.py` | a decision record is unindexed, misnumbered, or has no status |

### CI

`lint` (ruff + every pre-commit hook) · `types` (mypy --strict) · `test` (3.12 and 3.13, 90 %
coverage gate) · `web` · `e2e` · `analyze` (CodeQL, `python` and `actions`). The `web` and `e2e`
jobs guard on `apps/core/web` existing and stay green until it lands.

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

**v0.1 — the spine that runs.** In order: ~~`hera_tools`~~ → `hera_profiles` (git-backed mind
regions, `PromptBuilder`) → `hera_skillsets` → `hera_chats` (turn orchestrator, persisted event
stream) → `apps/core` → the end-to-end suite.

`hera_profiles` is the next one. `hera_chats` is the one to think about before starting it: it
is where a tool *result* has to become something persisted and rendered, and the event union in
`hera_providers` deliberately has no variant for one — it defines what a **model** emits, and a
tool result is not that. Whether `hera_chats` persists a superset of the union or the union
grows a variant is the first decision that turn orchestrator makes.

**The application is one package now.** `hera-core` at `apps/core/` holds the API and, under
`web/`, the SvelteKit interface — not two directories under `apps/`. See
[ADR 9](adr/0009-one-application-package.md), which supersedes the layout clause of ADR 1 and
ADR 6 and leaves everything else in both standing. It stays out of `packages/` on purpose: that
directory means *a library another project can consume*, and `tests/test_layering.py` scans it
and demands an allow-list per member. The application is the one thing that legitimately imports
everything.

**v0.2 — what makes her Hera.** `hera_memories` (embeddings, retrieval, caps, dedup, hits),
trace compaction and the context meter, `hera_promptevo` (dreaming and experience training).

**v0.3 — reach.** Hera as an MCP server so Claude Code can read her memory and skills, scheduled
dreaming, agent personas branching the mind repository, a coding agent profile.

## Working on this

`CLAUDE.md` is the map, `ARCHITECTURE.md` the layering, `CONTRIBUTING.md` the setup and the
loop. `uv sync --all-packages`, then `uv run pre-commit install` — the hooks run ruff, mypy and
the conventional-commit check, and CI runs the same hooks so the configuration cannot drift.

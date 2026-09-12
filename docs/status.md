# Status

Current state of the rebuild, so a new session can start without re-reading history. A snapshot,
not a changelog — historical detail and full rationale live in `versions/` and the ADRs.

**Updated:** 2026-09-10 · **Version:** v0.2.0 tagged, v0.2.1 in progress · **Strategy:** thin spine
first, then deepen

## Now: v0.2.1

### The turn was sending the wrong conversation ([issue #63](https://github.com/VoidEUW/hera/issues/63))

Fixed. Three duplication bugs in what went on the wire, all of the same shape — the request was
being *accumulated* rather than derived:

1. **The current question went out twice**, because it is persisted before the turn starts and the
   turn also appends it. Two identical consecutive user turns.
2. **Every earlier tool round was re-appended each round** — round four carried round one's
   `tool_call_id`s three times.
3. **Two rounds with nothing said between them were flattened** into one assistant message asking
   for both calls at once.

Qwen3.6, DeepSeek and GLM5.3 absorb all three; **GLM-4.7-Flash and GPT-OSS-20B do not** — they
re-greeted from turn two and produced unusable tool calls. The fix is one property, now stated in
`CLAUDE.md`: the record grows, and each round's messages are rebuilt from it.

**Still to do:** re-run the comparison against the real endpoints — GLM-4.7-Flash on the local GGUF
and via OpenRouter, GPT-OSS-20B, and Qwen3.6-35B to confirm nothing regressed. That is issue #63's
last unchecked box and it needs a machine with the weights on it.

### `hera__ask` and the stance vocabulary

Two coupled changes, landed in this order because `hera__ask`'s `kind` used to read from the
stance vocabulary ([versions/v0.2.1.md](versions/v0.2.1.md) § 4,
[ADR 17](adr/0017-a-stance-is-a-sentence-and-a-question-stands-alone.md)):

1. **`hera__ask` stands alone.** `kind` is now a closed `Literal["unsure", "blocked", "choice"]`
   in the tool's own schema — enforced by the SDK, so the prompt no longer spells out a
   vocabulary. `AnswerRequired.kind` stays a plain `str` so turns persisted before the set closed
   still load.
2. **Emotions/stances are gone entirely** ([ADR 17](adr/0017-a-stance-is-a-sentence-and-a-question-stands-alone.md),
   supersedes [ADR 3](adr/0003-emotions-as-tool-calls.md)). `hera__emotion`, the stance
   vocabulary, and the emotion card are removed. Nothing replaces them — a model that thinks
   something is wrong says so in prose.

Notes from the change:

- Only the *absence* is testable (`emotion` not in `TOOL_NAMES`, `GET /emotions` → 404) — the
  original problem needed a real endpoint to observe and can't be regression-tested either way.
- `hera__ask` had no standalone test before this (only integration coverage via `hera_chats` /
  `apps/core`); it has one now, including a call made outside a turn.
- Every fixture/toy-server double named `emotion` was renamed, so a grep for the removed tool
  doesn't return dozens of unrelated hits.
- `docs/tooling.md` § 4 still argues for the old direction (`emotion` with an argument) — left as
  written, with a note: the separate-tool conclusion it reached turned out right for reasons the
  doc didn't know yet.

## Timeline

| Version | State | Notes |
|---|---|---|
| v0.1 | shipped | spine: message in → model boundary → router → mind → turn orchestrator → SSE out |
| v0.2.0 | **tagged** | organise → produce → remember: projects, scratchpad, artifacts, memory (3 of 5 planned milestones — the other two moved, not dropped) |
| v0.2.1 | in progress | polish: `⌘K` palette, hotkeys, `hera__read_resource`, ADR 17 |
| v0.3.0 | planned | dreaming, sandbox, `hera-code` — see [versions/v0.3.0.md](versions/v0.3.0.md) |

Dreaming and the redesign pass both moved out of v0.2.0 on purpose — dreaming because every
dependency arrow points *into* it and none out, so deferring it leaves no half-built seam; the
redesign pass because its one load-bearing part (the drawer) was already built early with
artifacts. See [versions/v0.2.0.md](versions/v0.2.0.md) for the full reasoning.

## v0.2.0 milestones

| Milestone | Status | Branch | What shipped |
|---|---|---|---|
| M1 Projects | ✅ merged (`main`) | `feat/project-folders` (#10) | project CRUD, `/project/<id>`, `Select.svelte` (now every dropdown) |
| — | ✅ merged | `fix/mind-error-and-uncertainty` (#11) | `uncertainty`/`correction` mind regions, `hera__ask`, date-in-prompt, boot guard |
| — | ✅ merged | `fix/linear-turn-order` (#12) | turn renders in event order, not gutter-rows-then-prose |
| — | ✅ merged | `fix/repeated-tool-calls` (#13) | identical call capped at 2/turn; budget exhaustion ends in an answer |
| M2a Scratchpad | ✅ | `feat/chat-scratchpad` | per-chat scratch dir — [ADR 12](adr/0012-a-chat-has-a-scratchpad.md) |
| M2b Artifacts | ✅ | `feat/chat-artifacts` | `artifact_create/edit/read` — [ADR 13](adr/0013-an-artifact-is-a-file-she-publishes.md) |
| — | ✅ | (stacked on M2b) | skill resources — [ADR 14](adr/0014-skill-resources-are-readable.md) |
| M4 Memory | ✅ | `feat/memories` | markdown-file memories — [ADR 16](adr/0016-a-memory-is-a-file-and-all-of-them-are-in-the-prompt.md) |
| Sandbox | ❌ dropped, replanned | — | not needed for M2b after all; scoped as [ADR 15](adr/0015-running-code-in-a-container.md), scheduled v0.3 |

**PR stacking.** Branches were stacked, not independent: each carries an alembic migration on top
of the last, and a `~/.hera` used to review one branch needs every migration below it. Merged
bottom-up, each rebased onto `main` after the one below it squashed. `boot.check_revision` now
gives a clear error instead of alembic's raw traceback when a checkout skips a revision. Also:
after a squash merge, `mergeStateStatus: CLEAN` does not mean a correct diff for a branch still
based on the pre-squash tip — check `git diff --name-status origin/main HEAD` for deletions
before every merge.

**Test counts by stage:** v0.1 905 tests/98% + 48 vitest + 10 Playwright → M2a/M2b 1115/98% + 117
vitest + 23 Playwright → M4 (current) **1206 tests/98% + 112 vitest + 27 Playwright**. (Vitest and
pytest both dropped slightly with the emotion card's removal — its two properties moved to the
question card, which already had them.)

## Settled decisions

Each has a record in [adr/](adr/); read those before reopening one.

| | Decision | Why it matters day to day |
|---|---|---|
| [1](adr/0001-uv-workspace-monorepo.md) | One uv-workspace monorepo | `hera_storage` and `hera_prompts` moved in from their own repositories but keep a **domain-free contract**: no table, no chat, no `hera_*` import. Packages stay independently consumable — see *Reuse* below |
| [2](adr/0002-qwen-only-target-model.md) | Qwen3.6-35B is the only target | No harmony normalisation, no text call grammar, no second parser in the browser, no positional-argument fallback. XML prompt format, native tool calling |
| [3](adr/0003-emotions-as-tool-calls.md) | Emotions are tool calls | **Superseded by [17](adr/0017-a-stance-is-a-sentence-and-a-question-stands-alone.md).** What outlived it: what she *did* is an event variant, never something parsed back out of what she wrote |
| [4](adr/0004-mcp-as-the-tool-layer.md) | MCP is the tool layer | `~/.hera/mcp.json` in Claude-Desktop shape. Hera's own tools are an in-process MCP server, not a special case |
| [5](adr/0005-deterministic-skill-routing.md) | Skills are selected by code | The target model does not reliably notice a skill applies. Pinned → `/slash` → retrieval, all server-side, before the model sees the turn |
| [6](adr/0006-spa-over-json-sse-api.md) | SvelteKit over a JSON/SSE API | API renders no HTML; client types are generated from OpenAPI; server render stays authoritative at `done` |
| [7](adr/0007-fresh-start-no-legacy-import.md) | Empty `~/.hera/` | No importer. Boot refuses to run against a pre-v0.1 directory and tells you to move it aside; nothing is deleted |
| [8](adr/0008-github-flow-and-required-checks.md) | GitHub Flow, protected `main` | PR for everything, squash merge, linear history, required checks, zero required approvals (single maintainer) |
| [9](adr/0009-one-application-package.md) | One application package, `hera-core` | `apps/core/` holds the API and the web app; `packages/` stays libraries only, so the layering guard keeps meaning what it means |
| [10](adr/0010-chat-events-wrap-the-provider-union.md) | `ChatEvent` wraps `hera_providers.Event` | A skill selection, a tool result and a permission request are not model output. Two unions, one total mapping, still no parser — and `hera_providers` keeps its empty allow-list |
| [11](adr/0011-markdown-and-tex-in-the-browser.md) | Her prose is typeset in the browser | Markdown and TeX are drawn as what they are. The rule that stands is about *structure*: what she did is always an event variant, never something read back out of text |

Other constraints, decided but with no dedicated record: English everywhere with an i18n seam;
single-user login in v0.1 behind a multi-user-ready seam (`Depends(current_user)` on every route,
`owner_id` on every row); desktop-shaped interface, installable as a PWA on the phone.

## What exists

```
pyproject.toml            uv workspace root — ruff, mypy --strict, pytest, coverage, all shared
packages/hera_home/       where ~/.hera is; no dependencies, no I/O
packages/hera_storage/    vendored, unchanged in behaviour
packages/hera_prompts/    vendored, unchanged in behaviour
packages/hera_providers/  the model boundary: event union, Qwen adapter, transport, FakeProvider
packages/hera_permissions/ allow · deny · ask, resolved by pattern and profile
packages/hera_mcp/        the MCP server she *is*: ask, remember, forget, note, skill, search,
                          the scratchpad, the artifacts, and the ports they take
packages/hera_tools/      the MCP client: server lifecycle, the namespaced catalogue, dispatch
packages/hera_profiles/   the git-backed mind, behaviour traits, profiles, the PromptBuilder
packages/hera_skillsets/  SKILL.md packages, the router, usage counts
packages/hera_chats/      projects, chats, the persisted event stream, the turn orchestrator
apps/core/                hera-core: the FastAPI JSON/SSE API, alembic, the CLI
apps/core/web/            the SvelteKit interface, built into the directory the API serves
tests/                    repository-level guards (see below)
tests/e2e/                Playwright against the real application and FakeProvider
.github/                  CI, CodeQL, release, templates, CODEOWNERS, dependabot
docs/adr/                 seventeen decision records
```

## Foundation (`hera_providers`, `hera_permissions`)

- **`hera_providers.events` is the whole contract.** A new model capability is one new event
  variant, persisted by `hera_chats`, serialised by `apps/core`, rendered by its web app — never
  a new parser. `EVENT_ADAPTER` round-trips a single event, so persistence goes through the union.
- **A malformed tool call is not an exception.** Bad arguments arrive as
  `ToolCallReady.parse_error`, fed back to the model to self-correct. Real failures — unreachable
  endpoint, timeout, bad status, mid-stream disconnect — raise `ProviderError`; nothing from httpx
  escapes. `StreamInterrupted` persists partial events and closes the turn `cancelled`.
- **A tool call is announced before it finishes.** `tool_call_started` is streamed (id + name)
  from the fragment that *names* the call, never persisted — the started row and the ready row
  are one row keyed on call id, so a reload still renders correctly with strictly fewer events.

## `hera_mcp` (the server she is)

- Own package, separate from `hera_tools` (the client) — `hera_tools` never imports it.
- `ToolRegistry.from_config(builtin=...)` mounts it under `server.name` ("hera"); nothing is
  auto-mounted.
- Tools: `ask`, `remember`, `note`, `skill`, `search` (`emotion` removed by ADR 17) — namespaced
  `hera__*`, listed in `TOOL_NAMES`.
- `ask` is never *run*: `hera_chats` intercepts it by name before dispatch; called outside a turn,
  the body refuses.
- `remember`/`note` are listed but answer "not available in this deployment" until their backing
  packages exist — a model that can't see `remember` tells the person it can't remember, which
  beats a silent stub.
- `search` reaches DuckDuckGo through a `Searcher` port (`hera_core.search.DuckDuckGo`), no API
  key needed. Stays **allowed by default policy**: a card per lookup (3–4 per real question) would
  train click-through-without-reading; a `fetch` tool would deserve the card, `search` doesn't.
- Tests use a real `mcp.Client` over the SDK's in-memory transport, opened per test rather than
  via fixture (pytest-asyncio finalises fixtures in a different task than the SDK's task-affine
  anyio group expects).
- `hera_tools`'s own suite mounts a toy server, never hers — keeps "what fails is the client"
  clean of her behaviour.
- Verified against a real gateway too: `~/.hera/mcp.json` + Docker MCP Toolkit connects and
  dispatches alongside her four tools; `apps/core`'s `TestARealMcpServer` fakes only the model.

## `hera_tools` (the MCP client)

- Above `ToolRegistry`, nothing raises — every outcome (denied/misnamed/unreachable/timeout/
  failed) is a `ToolResult(ok=False, text=...)` the model can read and correct from.
  `ManagedServer` below it still raises.
- In-process servers aren't a special case — same client, same catalogue, same policy as remote
  ones.
- SDK is `mcp` 2.x. Note `httpx2` (the MCP SDK's own HTTP client), not `httpx`, for headers to a
  remote server.
- One client per worker task (anyio task groups are task-affine); calls queue to it, which keeps
  parallel calls parallel.
- A dead stdio server doesn't self-report: undetected, every later call fails forever with
  `MCPError("Connection closed")`. Detected explicitly and the connection retired instead.
- `~/.hera/mcp.json`: Claude-Desktop shape, `${VAR}` expansion, unset var is a hard error (a blank
  credential fails later and less clearly).

## `hera_profiles` (the mind)

- **Date is in the prompt, not a tool** — UTC always, plus local time if `config.toml` names an
  IANA zone (never a raw offset, which is wrong twice a year). A bad zone name degrades to UTC
  silently at render time but is refused at the settings route.
- **13 mind regions** (was 14 before ADR 17 removed `emotion_usage`). `uncertainty` and
  `correction` were the model's own idea when asked to review its prompt; both sit under
  `approach` (how she works a problem, not what she will/won't do), which also makes them
  evolvable. `uncertainty` needs `hera__ask` to mean anything — they shipped together.
- **Two write paths.** `MindRepository.write()` is the person's, opens every region including
  `safety`. `.propose()` is everything else's, raises `RegionLocked` on an owner-fixed region —
  the actual mechanism behind "add a rule without touching code."
- Git backend is the `git` binary, not a library binding: init/add/commit/log/show,
  `user.name`/`user.email`/`commit.gpgsign=false` pinned per invocation. Provenance rides a
  `Hera-Origin` trailer.
- A profile owns no text — only region toggles, overrides, traits, and skill pins by bare name.
- **Gotcha:** `sqlalchemy.ext.mutable` does not work under SQLModel — `__setattr__` overwrites the
  coerced `MutableDict`. `ProfileRepository.save()` flags the four JSON columns by name instead;
  an in-place edit followed by a bare `session.flush()` is silently lost.
- Everything synchronous, run in a worker thread by the turn orchestrator.

## `hera_skillsets`

- Retrieval works with **no model endpoint** by default (ADR 5): keyword overlap, IDF-weighted,
  scored against the skill's own description length. `Embedder` is an optional port; a raising
  embedder is treated as absent.
- Skill identity is the **directory name**, not frontmatter `name` — a mismatch is reported, never
  silently overridden.
- **Gotcha:** `description: Use when: …` is invalid YAML (the colon breaks the parse) and would
  silently drop the description. Frontmatter that fails to parse is re-read line by line and the
  failure is reported to the author.
- Nothing raises for bad content — a broken `SKILL.md` still loads carrying a `problems` list; a
  directory with none becomes a `BrokenSkill`.
- `missing` (pin, folder gone) and `dropped` (fit, didn't make the budget) are different fields
  with different fixes.

## `hera_prompts`

One field added: `Section.escape` (default `True`, the prior behaviour). `hera_profiles` sets
`escape=False` on slot sections and keeps `True` on regions — otherwise a slotted skill body
reaches the model XML-escaped (`if count &lt; limit`), reading as corrupted content.

## Memory (`hera_memories`, [ADR 16](adr/0016-a-memory-is-a-file-and-all-of-them-are-in-the-prompt.md))

One markdown file per memory under `~/.hera/memories/<key>.md`, filename as key, no retrieval —
every enabled memory is always in the prompt, under a token ceiling.

- No listing tool, by design: every enabled memory is already in her prompt, so reading them back
  would just spend context restating it.
- `hera__forget` disables, never deletes — the only thing that unlinks a memory is a person on the
  settings screen.
- Token count is an approximation (`ceil(len(text) / 4)`), named as one — a real count needs the
  active endpoint's own tokenizer, which the UI shouldn't depend on.
- Lives in `hera_home` (a directory), not `hera_storage` (a table) — its allow-list was written
  early, before the storage shape was decided.

## `hera_chats`

- `ChatEvent` wraps `hera_providers.Event` rather than extending it
  ([ADR 10](adr/0010-chat-events-wrap-the-provider-union.md)) — keeps `hera_providers`'s
  allow-list empty.
- `TurnEnd` (the model's per-round-trip stop) never reaches the browser; the orchestrator closes
  the turn once with `turn_closed`, whose reasons include "waiting for a person."
- `hera__ask` closes the turn (`awaiting_answer`/`AnswerRequired`) rather than blocking it; the
  reply resumes the same message via `TurnContext.resume` and becomes that call's `tool_result` —
  the model's side of the loop never learns a person was involved.
- The turn doesn't hardcode `hera__ask`'s name — it suspends on any name in
  `ChatsSettings.asking_tools`, filled in by `apps/core` from `hera_mcp.ASK_TOOL`.
- Identical call (tool + sorted-key arguments) capped at **2 per turn**; a 3rd returns a failed
  result quoting the earlier ones. Twice, not once, because the turn can't know which tools are
  idempotent — read-after-write is legitimately different each time.
- Tool-budget exhaustion now runs one final round with tools withheld, so the model summarises
  instead of stopping mid-lookup. Close reason stays `max_iterations`. Ceiling raised 8 → 12 now
  that repeats are capped.
- Calls issued alongside a `hera__ask` are dropped, not run — the question implies the rest is
  contingent on the answer.
- History is rebuilt from the event list every time, not from a stored column — preserves
  `tool_call_id` pairing; a call with no result gets a message saying it never ran.
- A call's *arguments* are replayed under every later question in history, unlike its result.
  `build_history` truncates a replayed string argument past
  `ChatsSettings.max_history_argument_chars` (a rule about size, not tool identity —
  `hera_chats` may not learn which tools are hers).
- A chat can pin skills (`chat.pinned_skills`), merged ahead of profile/project pins — most
  specific wins.
- `Tools` is a narrowing protocol `hera_chats` depends on — lets tests drive the loop without real
  MCP servers.

## `apps/core`

- **Streaming route commits before it streams**, then `expunge_all()`s. A `Depends`-provided
  session commits at teardown — after the last SSE byte — so without this the answer streamed
  correctly and then vanished on reload. Only caught because API tests use file-backed SQLite;
  in-memory's `StaticPool` shares one connection across sessions and hides the class of bug.
- SPA fallback is custom, not `html=True` (which only serves `index.html` for a *directory*, not
  `/chat/<uuid>`) — a 404 handler serves the index instead; the `/api` catch-all is registered
  before the mount so an unknown endpoint still answers JSON.
- `Policy(fallback=ASK)` + `DEFAULT_POLICY` allows `hera__*`, asks for everything else — an
  ordinary turn makes several of her own calls, and a card per one trains people to click through
  without reading.
- Embeddings are deliberately unwired: `SkillRouter.select()` runs synchronously in a worker
  thread, and threading the event loop down to an async embedder risks a subtle deadlock. The
  keyword fallback runs instead — the cost is ranking quality, not a missing feature.
- Artifacts are never served as `text/html` from Hera's own origin — content comes back as JSON,
  downloads as `application/octet-stream` + `nosniff`; the browser frame uses `srcdoc`, which has
  an opaque origin. Serving model-authored HTML from Hera's own origin would undo that sandbox in
  one header.

## Interface (web)

- One reducer (`turn.ts`) for both the live stream and the persisted list — tested to reduce to
  the same output either way, which is what "the server render is authoritative" means in code.
- The only parser in the browser is the SSE frame splitter (`EventSource` can't POST); everything
  past that is already-discriminated JSON from the server.
- An unknown event variant renders as a visible "unrecognised" row, never silently dropped — a
  missing feature and a broken one must not look identical.
- A tool call reads as a sentence ("called **Docker** fetch content"), qualified name on hover /
  under the permission card — no table of known tools, so an unfamiliar server doesn't look broken
  next to a familiar one.
- Gutter marks by what happened, not by which event carried it: a thought keeps the ocellus; a
  skill (routed or self-selected mid-task) gets a scroll; everything else gets a wrench.
- A question is drawn once out of three events (`hera__ask` call, `answer_required`,
  the synthesised `tool_result`) — `QuestionCard` is `PermissionCard` with a field instead of
  buttons, settled state read from the persisted `answer_given` event.
- Long tool result scrolls inside a fixed frame instead of pushing the answer off-screen.
- A fenced code block is a `<figure>` with a copy button; copy reads the DOM rather than a
  duplicated `data-` attribute.
- No card may use the "danger" colour for a stance or a question — a question she can ask is never
  an error (the rule outlived the removed emotion card, which is where it was learned).
- Copy (needs an answer) and *Try again* (doesn't) were gated on the same flag — a turn that
  failed before she said anything had no controls at all, which is the case someone is actually
  staring at wanting to retry. Decoupled.
- `busy` (send vs. Stop) and "a card is open" are different booleans — conflating them orphaned
  suspended turns behind a card the person could never reach again.
- A turn is one ordered list of blocks, not two (gutter rows, then all prose) — `reduce()` groups
  consecutive gutter rows into one block; prose and cards interleave in event order.
- Two `$effect` traps cost real debugging time and are worth remembering: assigning `scrollTop`
  inside an effect that reads state its own scroll handler writes, and calling an initialiser from
  an effect that both reads and writes the same state. One-time setup goes at component top-level.

## Settings

- Endpoints are registered in `config.toml`, editable on screen, applied without restart —
  `Services.use_provider()` swaps the client and the model name together, because pointing a new
  server at the old model's name just 404s.
- `config.toml` seeds from environment variables once, then wins — but `TUNING_FIELDS` are omitted
  on write unless they differ from the default, so a later default improvement isn't permanently
  shadowed by a value nobody actually chose. (This bit a real install: `timeout_s = 180.0` frozen
  from whichever version first wrote the file.)
- Read timeout: 3 min → **10 min** default, editable. It bounds *silence between stream chunks*,
  not total answer time — a local 35B model prefilling a long history plus a skill body can exceed
  3 minutes before the first token.
- API key is write-only — responses carry `api_key_set`, never the key. Omit on PATCH to keep,
  send empty string to clear.
- A probe failure ("nothing listening on that port") renders as a normal answer, not a 500 — the
  commonest fresh-install state, shown beside the models the endpoint *did* report.
- Attachments are a content field, not inlined text — `ChatMessage.content` is a string or a list
  of `TextPart | ImagePart`. Limits: 2 MB/text file, 12 MB/image, PNG/JPEG/WebP/GIF. A text-only
  endpoint gets an honest error rather than a silently dropped image.

## The guards

Rules that would otherwise rot are tests, not prose:

| Test | Fails when |
|---|---|
| `test_layering.py` | a package imports sideways or upwards, or reaches into `apps/`. Each package has an explicit allow-list; `hera_storage` and `hera_prompts` have an empty one |
| `test_workspace.py` | a member is missing from mypy's `files`, from coverage's `source`, or from the root `[tool.uv.sources]`; or two test modules would shadow each other |
| `test_docs.py` | a decision record is unindexed, misnumbered, or has no status |

## CI

`lint` (ruff + every pre-commit hook) · `types` (mypy --strict) · `test` (3.12 and 3.13, 90%
coverage gate) · `web` (prettier, eslint, svelte-check, vitest, build) · `e2e` (Playwright against
the real application) · `analyze` (CodeQL, `python` and `actions`).

**Known open:** CodeQL's `actions` queries report `actions/missing-workflow-permissions` five
times against `ci.yml`, which declares no `permissions:` block and runs every job with the
default `GITHUB_TOKEN` scope. Medium severity, below the ruleset threshold — fix is
`permissions: contents: read` at the top of `ci.yml`.

## Merging into `main`

`main` is guarded by the **`protect-main` ruleset**, not classic branch protection (the classic
API answers *"Branch not protected"*, which is misleading — read it with
`gh api repos/VoidEUW/hera/rulesets`). Requires linear history, squash merge only, resolved review
threads, and a CodeQL result. `require_code_owner_review` is off: the sole `CODEOWNERS` entry is
the only maintainer, so nobody could approve their own pull request — ADR 8 already specifies zero
required approvals.

- `.github/workflows/codeql.yml` must keep existing — the ruleset waits for a CodeQL result, and
  with no workflow nothing produces one, so every pull request blocks indefinitely.
- Leave the CodeQL query suite at the default. `security-and-quality` was tried; every finding it
  added was a false positive against this codebase's idioms (ruff and mypy already hold that bar),
  and because unresolved threads block the merge, a noisy query isn't just noise here.
- `mergeStateStatus: CLEAN` means no conflicts, not a correct diff — after a squash merge, a
  branch still based on the pre-squash tip reports clean while proposing to *undo* what exists
  only in the squash. Check `git diff --name-status origin/main HEAD` for deletions before
  merging; rebase with `git rebase --onto origin/main <old-base>`.
- Merge with `gh pr merge --squash --match-head-commit <sha>` — pins the merge to the commit the
  checks actually ran against.
- Retarget the branch above a stacked PR by hand after each merge:
  `gh pr edit <n> --base main`. Merging the base does not do this automatically.
- A force-push doesn't always fire `synchronize` — a pull request can sit with no checks reported
  and never satisfy the ruleset; closing and reopening it triggers the run.

## Releases and deployment

**Tags are the moving point.** Nothing ships off a branch; a tag produces a release, and a release
is what gets deployed.

| Tag | Releases |
|---|---|
| `v1.2.3` | the application |
| `hera-skillsets-v0.1.0` | one package, wheel attached |

`release.yml` rejects a package tag whose version disagrees with that package's `pyproject.toml`.

## Reuse from another project

A monorepo normally costs this; here it does not. Another project — `hera-code`, say — depends on
one package by naming its subdirectory:

```toml
[project]
dependencies = ["hera-skillsets"]

[tool.uv.sources]
hera-skillsets = { git = "https://github.com/VoidEUW/hera", subdirectory = "packages/hera_skillsets", tag = "hera-skillsets-v0.1.0" }
```

uv resolves that package's own `hera_*` dependencies from the same commit and subdirectory, so the
consumer declares one line and gets a consistent set. Prerequisite: every member another member
depends on needs `{ workspace = true }` in the root `[tool.uv.sources]`, which `test_workspace.py`
enforces.

Skills are not Python packages — a `SKILL.md` directory is content, synced into `~/.hera/skills/`
or pointed at directly by Claude Code. They live in the separate `hera-skills` repository.

## What comes next

1. **React to the build.** `docs/frontend.md` says the design language gets adjusted once there is
   something to argue with — run `uv run hera serve` and argue with it. Open questions it can now
   answer: the display face, whether the ocellus lands, where thinking lives, the exact palette.
2. **Her identity.** The 13 mind regions ship with placeholder text saying what belongs in each.
   Writing them is what makes her Hera — a text editor in Settings → Mind, not code.
3. **A real endpoint.** Everything so far runs against `FakeProvider`. Settings → Models now
   registers one, tests it, and lists what it reports — so this is a matter of finding out what
   Qwen3.6-35B actually does with the `xml` prompt layout and the tool catalogue.
4. **Deliberate gaps.** The `⌘K` palette (opens Settings for now), the mobile sheet, the embedder
   seam.
5. **Remaining tool surface.** `fetch` is still missing (she can find a page and not read it);
   PDFs are scoped for v0.1.0 but where extraction happens is open (see
   [tooling.md](tooling.md) § 6); the eventual split into `hera_code_mcp` and `hera_sandbox` is
   still a note, not a decision.

**v0.3.0** ([versions/v0.3.0.md](versions/v0.3.0.md)): dreaming and experience training, a
sandbox, scheduled dreaming, agent personas branching the mind repository, and **`hera-code`** — a
coding CLI on this workspace's packages, with its own built-in MCP server, that Hera reaches as an
ordinary `mcp.json` entry. The direction reverses: instead of Hera as an MCP server Claude Code
reads, she is the one reaching out.

## Working on this

`CLAUDE.md` is the map, `ARCHITECTURE.md` the layering, `CONTRIBUTING.md` the setup and the check
loop. `uv sync --all-packages`, then `uv run pre-commit install` — the hooks run ruff, mypy and
the conventional-commit check, and CI runs the same hooks so the configuration cannot drift.

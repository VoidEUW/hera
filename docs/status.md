# Status

Where the rebuild stands and what is settled, so a new session can pick up without re-reading
the history. Updated as milestones land — this file is a snapshot, not a changelog.

**Last updated:** 2026-08-28 · **Version:** v0.2 in progress · **Strategy:** thin spine first, then deepen

**v0.2 is planned in [versions/v0.2.0.md](versions/v0.2.0.md)** — five milestones, in the order
*organise → produce → make room → remember → reflect*.

**M1 and three fixes are on `main`**, merged bottom-up as #10 → #11 → #12 → #13:

| Landed as | What it was |
|---|---|
| #10 `feat/project-folders` | **M1.** Projects you can make, rename, remove and move chats between; the project screen at `/project/<id>`; `Select.svelte`, which is now every dropdown in the application |
| #11 `fix/mind-error-and-uncertainty` | **Two mind regions the model asked for** — `uncertainty` and `correction` — plus `hera__ask`, without which the first is advice she cannot act on; **the date in every prompt**; the boot guard below |
| #12 `fix/linear-turn-order` | A turn renders in the order it happened, rather than every gutter row and then all the prose |
| #13 `fix/repeated-tool-calls` | An identical call runs at most twice a turn, and spending the tool budget ends with an answer instead of a half-sentence |

**They were stacked rather than independent, for a concrete reason worth keeping.** Migration
`0004` lives on the first, so a `~/.hera` used to review it is stamped `0004`; checking out a
branch without that revision made alembic refuse to boot with `Can't locate revision identified
by '0004'`. Two branches that both touch the schema cannot be reviewed against one data
directory unless the later one contains the earlier, and everything after inherits the same
constraint — so they merged bottom-up, each rebased onto `main` after the one below it squashed.
`boot.check_revision` now catches that class of mismatch and says what to do rather than raising
alembic's stack trace.

**A squash merge makes the branch above it lie.** `mergeStateStatus: CLEAN` means no conflicts,
not a correct diff: a branch still based on the pre-squash tip proposes to *undo* whatever exists
only in the squash. Checking `git diff --name-status origin/main HEAD` for deletions before each
merge is what caught `.gitkeep` going missing, and it is worth doing every time.

**M2 is next, and it is two branches rather than one**, split where
[tooling.md](tooling.md) § 5 said it had to be: artifacts and the scratchpad want the same storage,
and answering them separately produces two.

| | |
|---|---|
| **M2a** | The scratchpad, and a tool call that knows which chat it is in — [ADR 12](adr/0012-a-chat-has-a-scratchpad.md) |
| **M2b** | Artifacts and skill resources — [ADR 13](adr/0013-artifacts-are-tool-calls-with-versions.md), [ADR 14](adr/0014-skill-resources-are-readable.md) |

**A third stage was planned and dropped, and the reason is worth keeping because the mistake is
easy to make twice.** The sandbox was pulled forward from *not in v0.2* on the assumption that
artifacts needed somewhere to run code. They do not: `markdown`, `code`, `mermaid`, `html` and
`svg` are content, and an HTML artifact is a sandboxed `iframe` in the browser rather than a
container on the host. Running code is load-bearing only for the *script-running* half of
Anthropic's skills, which is a smaller prize than a Docker dependency and a security claim to keep
true. [ADR 15](adr/0015-running-code-in-a-container.md) is written and stands — it answers the
question § 3 refused to let the work start without — and it is scheduled for **v0.3**.

**The thing that blocked both, and was not obvious:** no tool can know which chat it is in. Her
server is built once at startup with its ports bound, and `ManagedServer` runs every call as a
child of a worker task created at *connect* time — so a `contextvars.ContextVar` set around the
turn reads back empty in the tool, silently. It travels in MCP's `_meta` instead:
`ToolRegistry.dispatch` takes an opaque `context` mapping, `hera_mcp`'s tools take a `ctx: Context`
the SDK keeps out of the input schema, and the key travels through `ChatsSettings.chat_meta_key`
the way `hera__ask`'s name travels through `asking_tools`. Verified against the SDK before any of
it was designed around. `hera__remember(scope="chat")` has been missing exactly this since v0.1.

**M2a is built**, on `feat/chat-scratchpad` off `main`. What it turned up:

- **The `_meta` mechanism had to be verified against the SDK before it was designed around**, and
  it holds: `client.call_tool(..., meta=…)` arrives at `ctx.request_context.meta`, and a
  `ctx: Context` parameter is **excluded from the tool's input schema** — so the model does not
  see a `chat_id` field and cannot fill one in with a guess. There is a test asserting the schema
  has exactly `name`, `text` and `append` on it, because that exclusion is the whole safety
  argument and it is somebody else's behaviour.
- **A hand-built container drifts from `build_services` silently.** The suite assembles `Services`
  itself rather than calling the real wiring, so it was missing `chat_meta_key` — the turn ran,
  every call succeeded, and the only symptom was her scratchpad answering *this call is not part
  of a conversation* in the middle of a working conversation. `apps/core/tests/test_wiring.py` is
  the guard, and it drives the real registry rather than inspecting the wiring: a
  `scratchpad=` argument can be present and be `None`.
- **The containment check runs after `resolve`, not on the string.** A symlink in the scratchpad
  is a traversal that every string check reads as an ordinary filename, so both the write and the
  read are refused through it — refusing one and allowing the other would make the scratchpad a
  file reader for anything a link already points at.
- **A size refusal happens before the file is opened.** `open("wb")` truncates, so a check after
  it would answer *no* and destroy the plan in the same call.
- **The toy server in `hera_tools`' suite grew a tool**, which broke two tests asserting a count
  of 2 on an unrelated server. `TOY_TOOL_COUNT` now, so a test about a server being *unreachable*
  does not fail because a tool was added to the reachable one beside it. Same move on
  `apps/core`'s catalogue assertion, which now reads `hera_mcp.TOOL_NAMES` rather than six
  literals — spelled out, that test fails every time a tool is added and the fix is always to
  paste the name in.

**Three things came off the back of driving it against a real endpoint**, and all three are on the
same branch:

- **A tool call is announced before it is finished.** `tool_call_started` is a new
  `hera_providers` variant carrying the id and the name, emitted from the stream fragment that
  *names* the call rather than from the one that completes it. Until this, a turn spent the whole
  of a long argument with nothing on screen — and an artifact whose content is a 40 KB document is
  exactly that case, so this is a prerequisite for M2b rather than a nicety. It is **streamed and
  never persisted**, which makes the reducer's contract explicit: a reload has strictly fewer
  events and has to draw the same rows, and it does, because the started row and the ready row are
  one row keyed on the call id.
- **The gutter's verb column was too narrow for her own tool names.** `scratch write` and
  `scratch read` both clipped to `scratch …`, so the two rows a reader most needs to tell apart
  were the two it made identical. The column comment had predicted this exact failure; 8em now.
- **The read timeout was three minutes and is ten**, and it is editable on Settings → Models rather
  than only in `config.toml`. It is not a limit on how long an answer may take: httpx measures it
  between one piece of the response and the next, so what it bounds is *silence* — loading the
  weights, and prefilling a prompt that has grown a skill body and six rounds of history. A local
  35B asked for a whole HTML page fell off the end of three minutes, and what a person saw was
  `did not answer in time` under an answer that had been going fine.

1042 tests at 98 % coverage, plus 94 vitest and 12 Playwright. M2b starts from here.

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
| [11](adr/0011-markdown-and-tex-in-the-browser.md) | Her prose is typeset in the browser | Markdown and TeX are drawn as what they are. The rule that stands is about *structure*: what she did is always an event variant, never something read back out of text |

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
packages/hera_mcp/        the MCP server she *is*: emotion, ask, remember, note, skill, search, and their ports
packages/hera_tools/      the MCP client: server lifecycle, the namespaced catalogue, dispatch
packages/hera_profiles/   the git-backed mind, behaviour traits, profiles, the PromptBuilder
packages/hera_skillsets/  SKILL.md packages, the router, usage counts
packages/hera_chats/      projects, chats, the persisted event stream, the turn orchestrator
apps/core/                hera-core: the FastAPI JSON/SSE API, alembic, the CLI
apps/core/web/            the SvelteKit interface, built into the directory the API serves
tests/                    repository-level guards (see below)
tests/e2e/                Playwright against the real application and FakeProvider
.github/                  CI, CodeQL, release, templates, CODEOWNERS, dependabot
docs/adr/                 eleven decision records
```

**The foundation and capability layers are on `main`.** `hera_tools` merged as #6/#8 — 450
tests, 99 % coverage. `FakeProvider` means every layer built on top is testable without a model
running. The whole suite is 571 tests at 99 % coverage.

**The whole of v0.1 exists and the spine runs**, on four stacked branches off `main`:
`feat/hera-profiles`, `feat/hera-skillsets`, `feat/hera-chats`, `feat/hera-core`. A message
typed into the browser reaches the model boundary through the router, the mind and the turn
orchestrator, and comes back as Server-Sent Events the interface renders — verified in a real
Chromium against `FakeProvider`, including that a reload shows exactly what was streamed.

905 tests at 98 % coverage, plus 48 vitest and 10 Playwright. Profiles brought `hera_home` with
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

### What `hera_mcp` settled

- **Her own server is its own package.** `hera_tools` is the **client** — subprocess lifetimes,
  namespacing, timeouts, retries, true of anybody's MCP server. `hera_mcp` is the **server she
  is**, and everything in it is a statement about what Hera can do: the emotion vocabulary, the
  sentence the model reads before calling `remember`. Those change for unrelated reasons, and
  v0.3 serves this one over a transport of its own so Claude Code can attach to her.
- **The client no longer names her.** `ToolRegistry.from_config(builtin=...)` mounts the server
  under `server.name`, so `"hera"` is written in one place. `open()` used to construct an
  unwired copy of her server when given none; a default that quietly mounts four tools is
  something you discover from a catalogue listing rather than from the call site, and it is
  gone. Nothing is mounted unless the application mounts it.
- **The tools are `emotion`, `ask`, `remember`, `note`, `skill` and `search`** — `hera__*` once
  the client namespaces them, and `TOOL_NAMES` says so in code. `ask` is the one that is never
  *run*: `hera_chats` recognises it by name before dispatch and suspends the turn, and the body on
  the server refuses, which is what a caller reaching it from outside a turn deserves to be told.
  Three were wired in v0.1: `emotion`
  needs nothing, `skill` reaches `hera_skillsets` through a port, and `search` reaches
  DuckDuckGo through another. `remember` waits for `hera_memories` and `note` for somewhere to
  put a document; both are still listed and answer "not available in this deployment", because
  a model that cannot see `remember` concludes it cannot remember and tells the person so.
- **`search` is the one that leaves the machine**, and it is the one whose absence changed what
  she *said* rather than what she could do: with no way to look anything up she did not answer
  "I cannot check that", she guessed fluently. `Searcher` is a port like the rest and
  `hera_core.search.DuckDuckGo` is the adapter — no key, so a fresh install can search, and
  swapping it for SearXNG is a class and one line of wiring. It stays **allowed** by the default
  policy: a card before each of the three or four lookups a real question takes would be as
  unusable as one per emotion, and a search reads something public and changes nothing. A
  *fetch* tool is the one that would deserve the card.
- **Its tests use a real client, not a call to the function.** `mcp.Client` over the SDK's
  in-memory transport, so the schema, the description and the `is_error` convention are part of
  what is asserted. The client is opened per test rather than yielded from a fixture:
  pytest-asyncio finalises an async fixture in a different task, and the SDK's client owns a
  task-affine anyio group — the same trap `hera_tools` answers with a worker per server.
- **`hera_tools`' own suite mounts a toy server** instead of hers. What fails there should be
  the client; a stub called "hera" offering "emotion" would have been a copy of her server
  living in the package that must not know about it.

### MCP, end to end

Verified against a real gateway, not only against `FakeProvider`: `~/.hera/mcp.json` with
Docker's MCP Toolkit (`docker mcp gateway run`, stdio) connects and contributes its tools
alongside her four, and a dispatch round-trips — `docker__mcp-find` came back in 1.7 s,
`hera__emotion` in 24 ms. `apps/core`'s suite now has `TestARealMcpServer`, which runs a turn
with a real `ToolRegistry` and a real `MCPServer` and fakes only the model, so nothing between
the model and the tool is a stub.

### What `hera_tools` settled

- **Above `ToolRegistry`, nothing raises.** Denied, misnamed, unreachable, timed out, or a tool
  that failed on purpose — all of them are a `ToolResult` with `ok=False` and a `text` written
  for the model to read and correct itself with. `ManagedServer` below it still raises, so it
  is honest used on its own. A turn therefore needs no `try` around a tool call.
- **An in-process server is not a special case.** It is reached over the SDK's in-memory
  transport by the same client every other server is reached by, listed in the same catalogue,
  checked by the same policy. Her own four tools are one of these and now live in `hera_mcp`;
  this package neither imports it nor knows what is on it.
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

- **The date is in the prompt, and it is not a tool.** A model that does not know today's date
  answers "what is current" from its training data, confidently and a year late, and nothing on
  screen tells that apart from an answer that is merely wrong. `hera__search`'s description
  already said to use it "whenever the answer depends on what is true now"; the date is what
  makes that actionable. A `what_time_is_it` tool would spend a round trip on something free and
  would only be called by a model that already suspected it needed to. UTC always, plus the
  person's local time when `config.toml` names a zone — an IANA name, because an offset is wrong
  twice a year. The zone is on the **profile menu**, not in Settings: where you are is a fact
  about you, not about how she works. An unusable name degrades to UTC in `clock.render` and is
  refused by the route, which is deliberately opposite — a person typing into a screen should be
  told now, a turn already running should not fail over a file edited last week.
- **Fourteen regions, and the last two were the model's idea.** Asked to read its own prompt, it
  reported two gaps in the same shape: nothing said what to do when it is **unsure** of an
  answer, and nothing said what to do when it notices mid-task that it is **on the wrong track**.
  Both are behaviours it will have anyway — every model has some default for them — and a default
  that is nowhere in the mind is one nobody can find and nobody can change, which is the argument
  that gave `language` its own region. They sit under `approach` rather than under `conduct`,
  because being unsure and being wrong are part of *how she works a problem* rather than of what
  she will and will not do; that also makes them evolvable, which is right, since the useful
  version of "when should I ask?" is learned from conversations that went badly. `approach` became
  a group to hold the three.
- **`uncertainty` is half a sentence without `hera__ask`.** Telling her to ask when a question is
  worth asking, with no mechanism to ask one, produces a model that announces its confusion and
  then guesses anyway. The two shipped together for that reason.
- **Twelve regions, and which twelve has moved.** `grammar` is gone: it described the
  EMOTION/NOTE/TRACE/CALL text format that ADR 2 deleted, and shipping it would invite the model
  to use a call syntax nothing parses. `mem_overview` folded into `memory_instr`, and `mem_ex`
  waits for `hera_memories`. Then `emotion_vocab` left and `language` arrived: the stance list
  became data (a slot, `SLOT_EMOTIONS`, bound per turn) because the interface needs to know that
  *doubt* is cool, and answering in English became a region because a behaviour with no line in
  the mind is one nobody can find and nobody can change.
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
- **Two things suspend a turn now, through one mechanism.** `hera__ask` closes it with
  `awaiting_answer` and `AnswerRequired`; replying resumes the same message and the reply becomes
  that call's `tool_result`, so nothing on the model's side of the loop learns a person was in
  it. `docs/tooling.md` § 4 argued for generalising the permission path rather than building a
  second suspension beside it, and this is that — the only new machinery is a reply field.
- **The turn does not know `hera__ask` exists.** It takes `ChatsSettings.asking_tools` and
  suspends on a *name*; `apps/core` fills it in from `hera_mcp.ASK_TOOL`. A deployment that
  configures nothing runs the tool like any other and the server refuses it, which is the honest
  degradation. `hera_chats` naming a tool on her own server would be this package learning what
  Hera is.
- **An identical call runs at most twice a turn.** Same tool, same arguments — with the keys
  sorted, because a model does not emit them in a stable order and two calls differing only in
  that are one request. The third comes back as a failed result quoting what the earlier ones
  returned and saying the words did not work. Observed failure: asked for a figure that was not
  in the results, the model ran one search four times, spent its whole budget and was cut off.
  Every call *succeeded*, so nothing noticed. Twice rather than once because the turn cannot know
  which tools are idempotent: reading a file after writing it is the same call with a
  legitimately different answer, and a third inside one turn is a loop in every case worth
  designing for.
- **Spending the tool budget ends with an answer.** The loop used to stop the moment the ceiling
  was hit, so the last batch of results was never shown to the model and the turn ended on
  whatever it had said *before* going to look. There is now one final round with the tools
  withheld — an empty tool list is arithmetic, where telling a model in prose to stop is advice.
  The close reason stays `max_iterations`: *stopped looking and summarised* is not *finished*.
  The ceiling is 12, up from 8, which is affordable once the budget is not spent on repeats.
- **The calls beside a question are dropped rather than run.** She asked and stopped; running the
  rest would act on the assumption the question was about. History already says a call with no
  result never ran, so the model reads it correctly on resume.
- **Nothing raises into the caller's loop**, and there is no error module at all. A dead
  provider, a broken stream, a runaway tool loop: each closes the turn with a reason.
  `Turn.recorded` is correct at every moment, so a cancelled turn keeps the text that arrived.
- **History is rebuilt from the event list, not from a column.** One assistant turn becomes
  several wire messages — assistant-with-calls, one `tool` message per result, assistant again.
  Flattening loses the `tool_call_id` pairing and the model ignores the result *silently*. A
  call with no result still gets a message saying it never ran.
- **Text is coalesced before storage.** Hundreds of `text_delta` events become one; the variant
  is unchanged, so live view and reload still render the same thing.
- **A chat can pin skills.** `chat.pinned_skills`, merged by the turn ahead of the profile's and
  the project's pins — the most specific and most deliberate of the three wins the budget. The
  column is JSON, so `ChatRepository.save()` flags it the way `Project` and `Message` already
  do; an in-place edit followed by a bare flush is silently lost.
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
- **A tool call reads as an action, not as machinery.** `$lib/tools.ts` opens the qualified name
  up: *called **Docker** fetch content*, with `docker__fetch_content` on hover and under the
  permission card, because that is what a rule is written against. The server is set in the
  sentence rather than boxed — five chips down a gutter read as a form, the same five words in
  bold read as a list of things she did. The one liberty taken with somebody else's word is
  raising its first letter, because a lowercase proper noun mid-sentence reads as a typo.
  Otherwise it is a string transformation with **no table of known tools**: one would make an
  unfamiliar server look broken next to a familiar one.
- **Three marks in the gutter, split by what happened rather than by which event carried it.** A
  thought keeps the ocellus. A skill gets a **scroll** — whether the router selected it before
  the turn or she reached for it with `hera__skill` mid-task, because those are the same thing to
  a reader and letting the plumbing decide the picture is how a category stops looking like one.
  Everything else she reached for gets a **wrench**. Knowing those two names is not recognising
  tools in general: `hera__*` is her namespace and the interface already draws one of them as a
  card. Each mark sits on the ground colour and **breaks the hairline** rather than having it
  drawn through — an eye with a wire through it is not an eye.
- **A long tool result scrolls inside its row.** A skill body is a document arriving in a gutter
  row; it now sits in a fixed frame with a line count under it, instead of pushing her answer
  off the screen. A `text` block is no longer listed under the text it already showed.
- **A fenced code block has a copy button.** Rendered as a `figure` with a caption bar — the
  language on the left, *Copy* on the right — and the click is caught once on the container by
  an action, because Svelte cannot bind a handler to markup it did not render. What it copies is
  read off the DOM rather than carried in a `data-` attribute: an attribute would be a second
  copy of every program she writes and a second thing to escape correctly.
- **No stance she can hold is an error.** The emotion card was drawing *warm* in pomegranate,
  which beside `--danger` in a dark interface reads as an alarm — so *agree* looked like
  something had gone wrong. Warm and careful are both brass now, told apart by the glyph, and
  nothing in that component may be the danger colour.
- **The vocabulary is one list, editable.** Settings → Emotions writes `~/.hera/emotions.json`;
  the same list renders into the prompt per turn and picks the colour the card is drawn in. It
  is deliberately *not* in the tool description, which is fixed when the MCP server is built —
  a vocabulary you can edit on screen has to apply on the next turn rather than the next
  restart. **Reset** deletes the file, so "reset" and "never touched" are the same state and a
  later change to the shipped list still reaches you.
- **Skills can be started from the interface.** *Add a skill* writes the same `SKILL.md` a person
  would write by hand. The writing is in `apps/core`, not `hera_skillsets`: that package reads
  the skills directory and says it does not write to it, and a library that both discovers
  content and creates it ends up owning a format it was only meant to read. The row now reads
  author first, licence as a quiet chip after it, and the version on the right where a column of
  them can be compared with what a repository says is current.
- **An answer you did not want has three ways out.** Copy, edit the question, try again — a
  quiet row under each message that appears on hover or focus. Edit and try again are one
  request (`POST /chats/{id}/messages/{message_id}/redo`) because they are one idea: the
  conversation goes forward from this point differently. Pointed at an answer, the question
  above it is what gets replayed.
- **A redo deletes what came after, rather than flagging it.** `MessageRepository.truncate_from`
  removes the question and everything below it before the new turn starts. A chat *is* its
  message list — history is rebuilt from it — so a `superseded` column would mean every reader
  has to remember to filter, and the one that forgets shows the model a conversation nobody
  had. The browser drops the same messages optimistically, so the screen is never still
  showing an answer to a question that no longer exists.
- **A chat is a thing you can rename and throw away.** The rail's `⋯` opens rename — an input
  where the title was, not a prompt box — and delete behind a confirmation. `PATCH /chats/{id}`
  is the whole backend of it. A title typed by hand sticks, because `ChatRepository.touch()`
  only ever names a chat that has none; clearing it hands naming back to her.
- **The composer says what she is running on and what is switched on.** The model selector sits
  beside send and activates a registered endpoint without a restart, and a pill beside `＋`
  counts pinned skills and connected servers with the names in its tooltip. Retrieval's picks
  are deliberately not counted: this says what is *always* on, and a number that changed with
  every message would be noise. The Enter hint moved to the top right of the field and fades as
  soon as there is something to send.
- **A person can say which skills apply.** ADR 5 keeps the *model* out of that decision; this is
  the other half of the sentence. The composer's context pill opens a picker, and what it toggles
  is `chat.pinned_skills` — a new JSON column, migration `0003`. The turn merges chat pins ahead
  of the profile's and the project's, because the chat is the most specific and the most recent
  thing anybody said about this conversation. It is not a filter: retrieval still runs and can
  still add more. A pin whose folder is gone is *not* refused on the way in — the router already
  reports it as `missing`, and refusing here would mean a skill moved aside for an afternoon
  silently loses every pin that named it.
- **A skill row answers who wrote it.** `author`, `license`, `icon` and `version` come from
  frontmatter `hera_skillsets` still refuses to interpret, lifted into named fields in the API
  where the audience is a screen. The verified mark comes from `~/.hera/trusted.json` — skill
  id to SHA-256 — and has three states, because a skill you signed and somebody then edited is
  not the same thing as one you never signed. Nothing is verified by default and that is not a
  complaint; the signed registry it is a seam for does not exist yet.
- **Her prose is typeset, not dumped** — [ADR 11](adr/0011-markdown-and-tex-in-the-browser.md).
  `$lib/markdown.ts` renders Markdown and TeX and sanitises the result; `$lib/components/Prose`
  draws it, and `app.css` styles it, because `{@html}` output is out of reach of Svelte's
  scoped styles. Setext headings are disabled so `---` is always a rule rather than a promotion
  of the line above it, and `$…$` is refused around anything that looks like a price. The rule
  that has not moved is the one about structure: what she *did* is an event variant, never
  something read back out of prose. Her **thinking** goes through the same renderer, a step
  smaller and muted — it is written in the same notation her answers are.
- **The reading column is the measure.** `--column` is 68ch of the body face at 17px, measured
  in a browser with the webfont loaded — Georgia, the fallback, is a sixth wider, so the number
  is 612px and not the 710px you get from measuring too early. Before this the column was
  760px and only the prose was capped, so her answer stopped 100px short of the edge the user
  bubble, the cards and the composer all reached, and the whole message read as nudged
  off-centre.
- **A section waiting on a request keeps its heading.** The profile card's *About* block was
  hidden until `health` came back, so the menu grew under the pointer and an end-to-end test
  failed roughly one run in six — the click was sometimes faster than the round trip. The
  heading renders immediately with a line saying it is asking. Worth the note because the
  symptom was a flaky test and the cause was an interface that changed shape after opening.
- **An emotion is drawn once.** Its `tool_call_ready` renders as a card inline; the matching
  `tool_result` would otherwise fall through to a gutter row and draw the same thing twice. A
  *failed* emotion keeps its row — one she showed and the system refused is exactly what
  openness means you get to see.
- **Every popup is one frame** (v0.2 M1). `Select.svelte` owns every dropdown: the composer's pill
  as the trigger, the skill picker's panel as the list. The composer's two used to be a native
  `<select>` with `appearance: none`, which gave the frame back and left the *list* the platform's;
  everything else was bare native. The rail's `⋯` menus share the frame. Popups are anchored
  popovers with no scrim — the skill picker is a sheet because choosing skills is a task you go and
  do, and picking one value from four is not.
- **A turn is one list, in event order.** It used to be two — every gutter row, then all the
  prose — which reads correctly only for a turn that does its thinking up front. The moment she
  speaks, thinks again and speaks again, the second thought was drawn *above* the sentence that
  prompted it, and the turn could not be read downwards at all. `reduce` returns `blocks`: a run
  of consecutive gutter rows is one bordered block, and prose and cards sit between the runs.
  `activity` and `inline` survive as views over it rather than as two lists that had to stay in
  step. Prose no longer accumulates across a tool call, which was the same bug from the other
  side — text before and after a call merged, so the call was drawn below both halves of what it
  produced.
- **A question is drawn once too, out of three events.** The `hera__ask` call, the
  `answer_required` card and the synthesised `tool_result` are all about the same question, and
  only the card is a thing a person is meant to read. `QuestionCard` is `PermissionCard` with a
  field instead of buttons — same inline placement, same settled state read from a persisted
  event (`answer_given`) rather than inferred from what turned up afterwards.
- **`busy` and `blocked` are different questions, and conflating them was a bug.** Both this file
  and `docs/tooling.md` claimed the composer "already blocks while `awaiting` is non-empty".
  Nothing read that field. Sending past an open card writes a fresh assistant row, and the resume
  routes work from `latest_assistant` — so the suspended turn was orphaned and its card could
  never be answered. The composer is now closed while a card is open, and the card's own controls
  stay live, which is why the two cannot be one flag. `busy` still only decides send-versus-Stop:
  a suspended turn is not a running one, and offering **Stop** for something that already stopped
  is a lie about what is happening.

### What the settings rework settled

- **Endpoints are registered in `config.toml`, not in the environment.** There was no way to
  point her at a model without an environment variable and a restart, which made "try the
  current state" a research project. Several may be registered and one is active; ADR 2 fixes
  the model *family* the prompt is written for and says nothing about how many endpoints you
  may save. The file seeds itself from `HERA_PROVIDER_*` the first time it is written, and wins
  afterwards — a setting you can change on screen that quietly does not apply is worse than one
  that overrides a variable.
- **A change takes effect without a restart.** `Services.use_provider()` swaps the client and
  the model name together, because they are one decision: pointing a new server at the old
  model's name fails as an unhelpful 404 from somebody else's API. Ownership of the provider is
  opt-in, so a test's `FakeProvider` is never closed by a reconfiguration.
- **The API key is write-only.** Responses carry `api_key_set`, never the key. A masked string
  is something a person tries to edit and a client tries to send back, and both end with a key
  of asterisks saved to disk. An omitted key on a PATCH keeps what is stored; an empty one
  clears it.
- **Probing is a normal answer, not a 500.** "Nothing is listening on that port" is the
  commonest thing to be wrong on a fresh install, and it belongs on the screen you were already
  looking at — next to the list of models the endpoint *did* report, each with a button that
  fills the field.
- **One version, declared once and read back.** `apps/core/pyproject.toml` is where it is
  written; `hera_core.__version__` asks `importlib.metadata` for the installed distribution
  rather than repeating the number, `/health` reports it, and the interface holds it on
  `workspace.version` so a second place that shows it costs a field rather than a request. It is
  on the start screen, centred at the foot. `release.yml` now checks the application tag against
  that file the way it always checked a package tag, so `v1.2.3` cannot ship an About box saying
  something else.
- **New chat goes to the start screen.** It used to create a chat and navigate into it, which
  opened every conversation as an empty transcript — the one screen in the application with
  nothing on it — and left an empty row in the rail if you walked away. The start screen is
  already where beginning a conversation is designed to happen. A project's own **＋** carries
  the project through the store, the same way the first message does.
- **Two doors, two questions.** Settings is *how she works* — Models, Skills, Servers,
  Permissions, Mind, and Dreaming listed as v0.2. The profile card at the bottom of the rail is
  *you and this machine* — appearance, which of her answers, where your data is. Mixing them is
  how a person scrolls past six model fields to find a light-mode toggle.
- **Attachments are a field, not text.** The `＋` on the composer bar reads a file in the
  browser and sends it as data; the model gets it composed by `hera_chats.history.content_of`,
  and the interface draws a chip from a name, a size and a media type. Inlined, drawing that chip
  would mean hunting for a fence and a filename in the prose — a parser, and the one rule this
  project will not bend. `title_from` now takes only the opening paragraph, so a file under a
  question does not end up in the sidebar.
- **A picture is a content part.** `ChatMessage.content` is a string *or* a list of
  `TextPart | ImagePart`, and `content_of` is the only place that decides which. A message with
  no picture in it stays a bare string on the wire, because that is the shape every local server
  has been serving since before parts existed and being unremarkable is worth more than being
  uniform. Limits: 2 MB a text file, 12 MB a picture, PNG/JPEG/WebP/GIF. Whether the endpoint
  behind the active model can *see* is the endpoint's business — a text-only server answers with
  an error, and that error is the honest one.

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

`gh pr merge --squash --match-head-commit <sha>` is what to use, and it worked for the whole
v0.2 M1 stack. `--match-head-commit` is the point rather than a flourish: it pins the merge to
the head you actually ran the checks against, so a push landing between the check and the merge
stops it instead of shipping something unverified.

Two things that cost time and are not obvious:

- **Retarget the branch above by hand.** Merging the base of a stacked pull request does not
  retarget the one on top of it; the PR keeps pointing at a branch that no longer moves. Set it
  with `gh pr edit <n> --base main` after each merge.
- **A force-push does not always fire `synchronize`.** Twice here the rebased head landed and no
  workflow ran, so the pull request sat with *no checks reported* and could never satisfy the
  ruleset. Closing and reopening the pull request triggers the run.

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

**v0.1 is spine-complete.** ~~`hera_tools`~~ → ~~`hera_mcp`~~ → ~~`hera_profiles`~~ → ~~`hera_skillsets`~~ →
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
3. **A real endpoint.** Everything so far runs against `FakeProvider`. Settings → Models now
   registers one, tests it, and lists what it reports — so this is a matter of picking the right
   name and finding out what Qwen3.6-35B actually does with the prompt: the `xml` layout, the
   tool catalogue, the emotion vocabulary.
4. **The gaps left on purpose.** The command palette behind `⌘K` (it opens Settings for now),
   the mobile sheet, and the embedder seam. ~~Project instructions in the interface~~ landed with
   v0.2's M1 — the rail makes and renames projects, and `/project/<id>` edits one.
5. **The rest of the tool surface.** `hera__search` now exists — see below — but `fetch` does
   not, so she can find a page and not read it. That and the rest of what using the build argued
   for (a per-chat scratchpad, an emotion that can ask a question back, artifacts, and the
   eventual split into `hera_code_mcp` and `hera_sandbox`) are written up in
   [tooling.md](tooling.md). Notes rather than decisions: nothing there has an ADR yet.

**PDFs are in v0.1.0.** Reading them is scoped in rather than deferred — a paper, a spec and a
scanned invoice are ordinary things to put in front of her, and the composer currently refuses
all three. Where the extraction happens is open; see [tooling.md](tooling.md) § 6.

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

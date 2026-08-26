# Status

Where the rebuild stands and what is settled, so a new session can pick up without re-reading
the history. Updated as milestones land — this file is a snapshot, not a changelog.

**Last updated:** 2026-08-26 · **Version:** v0.1 in progress

---

## The short version

Hera is being rebuilt from an empty repository. The previous version — one FastAPI application
with Jinja and HTMX, a German interface, a hand-written tool registry and a text call grammar
around GPT-OSS-20B — is retired to [prototype.md](prototype.md) and is wrong about everything
structural.

The replacement is a **uv-workspace monorepo**: small libraries under `packages/`, a FastAPI
JSON/SSE API at `apps/api`, a SvelteKit interface at `apps/web`. Tools come from **MCP servers**,
know-how from **`SKILL.md` skills**, and the target model is **Qwen3.6-35B** exclusively.

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

Other constraints that are decided but did not need a record: English everywhere with an i18n
seam; single-user login in v0.1 behind a multi-user-ready seam (`Depends(current_user)` on every
route, `owner_id` on every row); desktop-shaped interface, installable as a PWA on the phone.

## What exists

```
pyproject.toml          uv workspace root — ruff, mypy --strict, pytest, coverage, all shared
packages/hera_storage/  vendored, unchanged in behaviour
tests/                  repository-level guards (see below)
.github/                CI, release, templates, CODEOWNERS, dependabot
docs/adr/               eight decision records
```

Nothing else yet. `hera_providers` is next.

### The guards

Rules that would otherwise rot are tests, not prose:

| Test | Fails when |
|---|---|
| `test_layering.py` | a package imports sideways or upwards, or reaches into `apps/`. Each package has an explicit allow-list; `hera_storage` and `hera_prompts` have an empty one |
| `test_workspace.py` | a member is missing from mypy's `files`, from coverage's `source`, or from the root `[tool.uv.sources]`; or two test modules would shadow each other |
| `test_docs.py` | a decision record is unindexed, misnumbered, or has no status |

### CI

`lint` (ruff + every pre-commit hook) · `types` (mypy --strict) · `test` (3.12 and 3.13, 90 %
coverage gate) · `web` · `e2e`. The `web` and `e2e` jobs guard on their directories existing and
stay green until `apps/web` lands. Required on `main`.

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

**v0.1 — the spine that runs.** In order: `hera_providers` (httpx streaming, Qwen adapter for
`reasoning_content`/`<think>` and parallel `tool_calls`, and `FakeProvider` — the thing that
makes every layer above testable without a model) → `hera_permissions` + `hera_tools` →
`hera_profiles` (git-backed mind regions, `PromptBuilder`) → `hera_skillsets` →
`hera_chats` (turn orchestrator, persisted event stream) → `apps/api` → `apps/web` → the
end-to-end suite.

`hera_prompts` still needs vendoring alongside `hera_storage`. Its ruff `select` is narrower
than the root's, so unifying it may surface annotation findings.

**v0.2 — what makes her Hera.** `hera_memories` (embeddings, retrieval, caps, dedup, hits),
trace compaction and the context meter, `hera_promptevo` (dreaming and experience training).

**v0.3 — reach.** Hera as an MCP server so Claude Code can read her memory and skills, scheduled
dreaming, agent personas branching the mind repository, a coding agent profile.

## Working on this

`CLAUDE.md` is the map, `ARCHITECTURE.md` the layering, `CONTRIBUTING.md` the setup and the
loop. `uv sync --all-packages`, then `uv run pre-commit install` — the hooks run ruff, mypy and
the conventional-commit check, and CI runs the same hooks so the configuration cannot drift.

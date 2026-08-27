# CLAUDE.md — Hera

A map of this repository, not a changelog. Keep it short: the previous version of this file grew
to 98 KB of accumulated history and stopped being readable. It is archived as
`docs/prototype.md` — useful for *why* decisions were made, wrong about everything structural.

Hera is a self-hosted agentic chat space: a uv workspace of small libraries, a FastAPI
application, and a SvelteKit interface, talking to a local Qwen3.6-35B over an
OpenAI-compatible endpoint.

## Read first

- `docs/status.md` — where the rebuild stands, what is settled, what is next. Start here
- `ARCHITECTURE.md` — the packages, the layering rule, the shape of a turn
- `docs/adr/` — why the structure looks like this; read 2 (Qwen only), 3 (emotions as tool
  calls) and 5 (deterministic skill routing) before changing model-facing behaviour
- `docs/tooling.md` — what she should be able to reach for and cannot. Notes, not decisions;
  read it before adding a tool, and read § 1 before concluding she has no search *on purpose*
- `CONTRIBUTING.md` — setup, the check loop, branching
- `docs/README.md` — what the prototype document is still good for, and what it is wrong about

## Commands

```bash
uv sync --all-packages
uv run ruff check . && uv run ruff format --check .
uv run mypy                                         # strict
uv run coverage run -m pytest && uv run coverage report
uv run pytest -m e2e                                # Playwright against FakeProvider
uv run hera serve
```

`-m "not e2e and not live"` is the fast loop. `live` marks anything that needs a real model
endpoint; it never runs in CI.

## Rules that are not negotiable

**Imports point downwards.** The table in `ARCHITECTURE.md` is the authority, and
`tests/test_layering.py` enforces it. `hera_storage`, `hera_prompts`, `hera_providers`,
`hera_permissions` and `hera_mcp` import no other `hera_*` package; the first two contain no
domain concept at all and must stay liftable into an unrelated project.

**Two MCP packages, and the difference matters.** `hera_mcp` is the server she *is* —
`hera__emotion`, `hera__remember`, `hera__note`, `hera__skill`, `hera__search`, and the ports
the last four take. `hera_tools` is the client she *has*, and it does not know the other exists: it mounts
whatever in-process server the application hands it, under that server's own name. Her tool
descriptions are prompt text; edit them in `hera_mcp` and her behaviour changes.

**One event union.** `hera_providers` defines what a model can emit; everything above consumes
it. If you are writing a parser for model output outside that package, something is wrong — the
answer is almost always a tool call.

**No second parser in the browser.** The frontend renders event variants it is given. This is
the single largest source of bugs in the previous version and it is designed out. Typesetting
her prose as Markdown and TeX is not that parser and may not become one — it draws text as what
it is and reads no meaning back out of it. See ADR 11.

**The server render is authoritative.** The client replaces its optimistic view with the
persisted event list at `done`.

**Skill selection is code.** Never build a feature that depends on the model noticing a skill is
relevant; the target model does not. See ADR 5.

**English everywhere** — code, comments, commits, prompts, stored content, UI strings. UI text
goes through i18n so a German locale can be added later.

**Tables** carry a package-prefixed `__tablename__`; cross-package references are bare `UUID`
columns, never `ForeignKey`; migrations live in `apps/core`.

## What lives in `~/.hera`

| | |
|---|---|
| `hera.sqlite3` | everything relational |
| `mind/` | a real git repository, one file per mind region |
| `skills/<name>/SKILL.md` | skill packages |
| `mcp.json` | MCP servers, in the Claude-Desktop `mcpServers` shape |
| `config.toml` | registered model endpoints, written by the interface |
| `trusted.json` | **where trusted skills are recorded** — optional |
| `emotions.json` | her stance vocabulary, when it has been changed — optional |

`trusted.json` is the only thing that can put a *verified* mark on a skill, because a skill
vouching for itself has vouched for nothing. It maps an identifier to the SHA-256 of the content
you accepted:

```json
{ "skills": { "tdd": "9f2c…" } }
```

`hera_skillsets` digests each `SKILL.md` (it is already holding the bytes); `hera_core.trust`
decides what the digest means, because the same file will cover MCP servers and neither package
may import the other. Three verdicts: **verified**, **modified** — listed but the content has
changed since, which is worth saying loudly — and **unknown**, which is the ordinary state and
not a complaint. No file means nothing is verified; the signed registry this is a seam for does
not exist yet.

**Her vocabulary is data, her behaviour is prose.** The stances she can show live in
`emotions.json` (`hera_mcp.DEFAULT_EMOTIONS` until something is changed), edited on
Settings → Emotions, rendered into the prompt per turn *and* used to colour the card — one list,
so the two cannot disagree. Which language she answers in is the `language` mind region, edited
on Settings → Mind like every other behaviour.

## State of the build

See `docs/status.md` — kept there so this file stays a map rather than turning back into a
changelog.

Commit and push only when asked. Branch first — `main` is protected.

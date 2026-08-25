# CLAUDE.md — Hera

A map of this repository, not a changelog. Keep it short: the previous version of this file grew
to 98 KB of accumulated history and stopped being readable. It is archived as
`docs/prototype.md` — useful for *why* decisions were made, wrong about everything structural.

Hera is a self-hosted agentic chat space: a uv workspace of small libraries, a FastAPI
application, and a SvelteKit interface, talking to a local Qwen3.6-35B over an
OpenAI-compatible endpoint.

## Read first

- `ARCHITECTURE.md` — the packages, the layering rule, the shape of a turn
- `docs/adr/` — why the structure looks like this; read 2 (Qwen only), 3 (emotions as tool
  calls) and 5 (deterministic skill routing) before changing model-facing behaviour
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
`tests/test_layering.py` enforces it. `hera_storage`, `hera_prompts`, `hera_providers` and
`hera_permissions` import no other `hera_*` package; the first two contain no domain concept at
all and must stay liftable into an unrelated project.

**One event union.** `hera_providers` defines what a model can emit; everything above consumes
it. If you are writing a parser for model output outside that package, something is wrong — the
answer is almost always a tool call.

**No second parser in the browser.** The frontend renders event variants it is given. This is
the single largest source of bugs in the previous version and it is designed out.

**The server render is authoritative.** The client replaces its optimistic view with the
persisted event list at `done`.

**Skill selection is code.** Never build a feature that depends on the model noticing a skill is
relevant; the target model does not. See ADR 5.

**English everywhere** — code, comments, commits, prompts, stored content, UI strings. UI text
goes through i18n so a German locale can be added later.

**Tables** carry a package-prefixed `__tablename__`; cross-package references are bare `UUID`
columns, never `ForeignKey`; migrations live in `apps/api`.

## State of the build

v0.1 is in progress. Order: workspace skeleton → `hera_providers` → `hera_permissions` +
`hera_tools` → `hera_profiles` → `hera_skillsets` → `hera_chats` → `apps/api` → `apps/web` →
end-to-end suite. `hera_memories` and `hera_promptevo` (dreaming, experience training) are v0.2;
Hera as an MCP server and agent branching are v0.3.

Commit and push only when asked. Branch first — `main` is protected.

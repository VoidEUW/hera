# Contributing

## Setup

```bash
git clone https://github.com/VoidEUW/hera.git
cd hera
uv sync --all-packages
cd apps/web && npm ci
```

One checkout, one sync. Every library is a workspace member under `packages/`, so an edit in one
is visible to the others immediately with no reinstall.

## The loop

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run coverage run -m pytest && uv run coverage report   # gate: 90 %
cd apps/web && npm run check && npm run test:unit
uv run pytest -m e2e                                      # Playwright, no model needed
```

`pre-commit install` runs the fast half of this before every commit.

## Branching — GitHub Flow

`main` is always releasable and protected. Everything else is a short-lived branch off `main`:

| Prefix | For |
|---|---|
| `feat/` | new behaviour |
| `fix/` | a bug |
| `chore/` | tooling, dependencies, CI |
| `docs/` | documentation only |
| `refactor/` | structure, no behaviour change |

Open a pull request, let CI and CodeRabbit run, squash-merge, delete the branch. No long-running
branches, no direct pushes to `main`, no merge commits — history stays linear.

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
`feat(chats): stream tool results as events`. The type drives the changelog.

## Writing code here

- **Imports point downwards.** See the table in [ARCHITECTURE.md](ARCHITECTURE.md). A package
  importing from a package above it is a bug, and CodeRabbit is told to flag it.
- **Typed, strictly.** `mypy --strict` passes with no `# type: ignore` that lacks a reason on the
  same line. `from __future__ import annotations` at the top of every module.
- **Everything is English** — code, comments, docstrings, commit messages, UI strings, prompts
  and stored content. User-visible text goes through the i18n layer so a German locale can be
  added without touching components.
- **New table?** Prefix `__tablename__` with your package's prefix and add an Alembic revision in
  `apps/api`. Cross-package references are bare `UUID` columns, never `ForeignKey`.
- **New model capability?** One new variant in the `hera_providers` event union, one branch where
  it is persisted, one branch where it renders. If you are writing a parser, stop and check
  whether it should be a tool call instead.
- **Tests are not optional.** A package without a test for the behaviour you added does not
  reach 90 % and CI fails. LLM behaviour is tested against `FakeProvider`, never a live model —
  anything needing a real endpoint is marked `@pytest.mark.live` and stays out of CI.

## The two foundation packages

`hera_storage` and `hera_prompts` live in `packages/` like everything else, but they are held to
a stricter contract: **no domain concept, and no import of any other `hera_*` package — not even
each other.** `hera_storage` has no table and no chat; `hera_prompts` does not know what a tool,
a memory or a skill is. If you catch yourself typing "chat" in either, something is wrong.

Both must stay liftable into a project that has nothing to do with Hera.
`tests/test_layering.py` gives them an empty allow-list, so a stray import fails the build. See
[ADR 1](docs/adr/0001-uv-workspace-monorepo.md).

## Using one package somewhere else

Every member of `packages/` is a real distribution with its own name, version and build
backend, so another project can depend on exactly one of them without cloning the workspace or
pulling in anything else:

```toml
# in the other project's pyproject.toml
[project]
dependencies = ["hera-prompts"]

[tool.uv.sources]
hera-prompts = { git = "https://github.com/VoidEUW/hera", subdirectory = "packages/hera_prompts", tag = "hera-prompts-v0.1.2" }
```

Pin a **tag**, not a branch — a branch means the consumer silently moves whenever this
repository does. Package releases are tagged `<package>-v<version>`; the application's own
releases are plain `v<version>`.

While developing both sides at once, point at the checkout instead:

```toml
hera-prompts = { path = "../hera/packages/hera_prompts", editable = true }
```

To cut a package release, bump `version` in its `pyproject.toml` and tag:

```bash
git tag hera-prompts-v0.1.3 && git push origin hera-prompts-v0.1.3
```

`uv build --package hera-prompts` produces the wheel, identical to what a standalone repository
would have built — publishing to an index later needs no restructuring.

**Skills are not Python packages.** A `SKILL.md` directory is content: consume it with a git
clone or a sparse checkout, or let `hera_skillsets` sync it into `~/.hera/skills/`. The same
directory can be pointed at by Claude Code.

## Architecture decisions

Anything that changes the shape of the system gets a file in [docs/adr/](docs/adr/): the context,
the decision, the consequences. Numbered, never edited after the fact — superseded instead.

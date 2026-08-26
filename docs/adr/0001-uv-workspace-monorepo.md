# 1. One uv-workspace monorepo

- Status: accepted
- Date: 2026-08-26

## Context

The previous generation of Hera was one FastAPI application with `src/backend`, `src/core` and
`src/www`, roughly 42 leaf routers, and no seam anywhere. The design notes for `hera_storage`
and `hera_prompts` describe the intended replacement as eight libraries, each in its own
repository, with `heraAPI` on top. Two of those libraries — `hera-storage` and `hera-prompts` —
were built that way first and are finished.

Eight repositories for a single maintainer means eight CI setups, eight release cycles, and a
multi-pull-request dance for every change that crosses a boundary. One flat application means no
boundary at all, which is what we are trying to get away from.

Keeping only the two finished libraries outside was considered and rejected. They are private
repositories, so CI would have needed a personal access token and a checkout of each one beside
this repository just to resolve a path dependency — a permanent piece of machinery, and a secret
that expires, in exchange for a separation nothing else was enforcing.

## Decision

`hera` is a single **uv workspace**. Every library is a member under `packages/`, including
`hera_storage` and `hera_prompts`; the application is `apps/api` and the interface is `apps/web`.
One lockfile, one CI run, one CodeRabbit configuration, atomic cross-package changes, no secrets
needed to build.

The two foundation libraries keep their contract even though they now live here: **they contain
no domain concept and import no other `hera_*` package — not even each other.** `hera_storage`
has no table and no chat; `hera_prompts` does not know what a tool, a memory or a skill is.
Either must be liftable into an unrelated project unchanged.

That contract is checked rather than trusted. `tests/test_layering.py` holds an explicit
allow-list per package and fails on any import that points sideways or upwards; both foundation
packages have an empty allow-list, and `hera_storage` is named explicitly by each package that
persists something instead of being treated as universally available — so the one package that
must *not* reach for it stays visible.

## Reuse is not lost

A monorepo usually trades away the ability to consume one library on its own. Here it does not,
because every member stays a real distribution with its own name, version and build backend. A
separate project depends on exactly one package by pointing at its subdirectory:

```toml
[project]
dependencies = ["hera-prompts"]

[tool.uv.sources]
hera-prompts = { git = "https://github.com/VoidEUW/hera", subdirectory = "packages/hera_prompts", tag = "hera-prompts-v0.1.2" }
```

Only that package and its own dependencies are installed; the rest of the workspace is not
fetched, built or imported. `uv build --package hera-prompts` produces the same wheel a
standalone repository would, so publishing to an index later needs no restructuring.

Verified end to end: installing `hera-storage` this way into an unrelated project resolves
`sqlmodel` and `pydantic-settings`, and nothing else from the workspace comes with it.

## Consequences

- Their standalone repositories become upstream history rather than a live dependency. Changes
  land here from now on.
- Package versions move independently of the application's. Releases are therefore tagged
  `<package>-v<version>` (`hera-prompts-v0.1.2`) next to the application's plain `v<version>`,
  so a consumer can pin one library without pinning Hera.
- Nothing physically stops `hera_chats` from importing `hera_profiles`' internals. The layering
  test and CodeRabbit's path instructions are the enforcement; the rule is written down in
  `ARCHITECTURE.md`.
- Contributors need one checkout and one `uv sync`.
- If a package ever needs its own repository again, it can be extracted with its history intact.
  The import path does not change, because it never depended on the repository boundary.

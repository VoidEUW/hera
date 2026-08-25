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

## Consequences

- Their standalone repositories become upstream history rather than a live dependency. A change
  now lands here; syncing it back out is a manual export, which is the trade for not maintaining
  two release paths.
- Nothing physically stops `hera_chats` from importing `hera_profiles`' internals. The layering
  test and CodeRabbit's path instructions are the enforcement; the rule is written down in
  `ARCHITECTURE.md`.
- Contributors need one checkout and one `uv sync`.
- If a package ever needs its own release cadence, it can be extracted with its history intact.
  The import path does not change, because it never depended on the repository boundary.

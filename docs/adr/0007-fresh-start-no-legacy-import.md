# 7. Start from an empty `~/.hera/`

- Status: accepted
- Date: 2026-08-26

## Context

The existing installation holds 23 chats and 280 messages, 13 memory objects, 18 skill and
subconscious entries, five training documents, and a `mind/` git repository with 160 commits of
real history. It also holds four generations of migration debris —
`entities_legacy_v02`, `global_memory_legacy_v02`, `strategies_legacy_v02`,
`prompt_variants_legacy_v03` — left in place by migrations that renamed rather than dropped.

Carrying that forward means writing and testing an importer against a schema that is itself the
product of three earlier importers, for content whose main value is sentimental.

## Decision

v0.1 starts from an empty `~/.hera/`. There is no importer.

The old directory is **never touched**: boot detects a pre-v0.1 installation (a `hera.db` file,
or `*_legacy_v0*` tables) and refuses to start, telling the user to move it aside as
`~/.hera-legacy`. Nothing is deleted, and the old application still runs against it.

## Consequences

- The new schema is designed for what Hera is now, with no compatibility shapes in it.
- Roughly 160 commits of mind history and a handful of hand-curated memories are lost as *live*
  state. They remain readable on disk, and anything genuinely worth keeping can be typed back in
  — which is a few minutes of work, against days of importer plus tests.
- If an import is ever wanted, it can be written later as a standalone command against a frozen,
  well-understood target schema. That is a strictly easier problem than doing it now.

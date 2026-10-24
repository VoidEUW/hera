# 23. Permission rules are kept in a file, laid over the policy Hera ships with

- Status: accepted
- Date: 2026-10-22

## Context

Settings → Permissions was a read-only list, and "always" on a confirmation card changed the
policy in memory only: the next restart forgot it
([#109](https://github.com/VoidEUW/hera/issues/109)). The card's own docstring sent people to the
Permissions screen "where they can see what they are doing" — a screen that could neither change
anything nor show what would last.

Two things had to be settled: where a person's rules live, and what happens to the rules Hera
ships with (`hera__*` is allowed, because her own tools change nothing outside her and a card for
each would teach people to click through cards).

## Decision

**A person's rules live in `~/.hera/permissions.json` and are laid over the built-in policy at
boot.** The file is `{fallback, rules}` where each rule is `{pattern, decision, reason, name,
source}`; it records *what the person decided*, not a copy of what shipped. `hera_permissions` stays
pure — no I/O, no file — and `hera_core.permission_rules` owns the file.

- **The same bargain as `config.toml`:** the file means *what I decided*, not *what the defaults
  were the day I installed it*, so a better built-in rule later reaches everybody who has not
  overridden it. A fallback set back to the shipped one is forgotten rather than recorded.
- **A shipped rule can be changed but not deleted.** Changing it writes a rule of the person's own
  on that pattern; deleting that override puts the shipped one back.
- **A rule has a `name`** — display only, never matched on, because the pattern is the identity and a
  name that changed what a rule covers would be a second pattern nobody reads. A rule made from a
  card answer is named automatically (*Allowed from a card · fs read_file*) and stays marked as
  coming from a card.
- **One mechanism for the screen and the card** (`hera_core.rulebook`): the file, the policy the
  tool layer asks, and the orchestrator holding it change together, under one lock, with the file
  replaced atomically. "Always" on a card goes through the same `remember`, so it survives.
- **The routes:** `POST /permissions/rules`, `PATCH` and `DELETE /permissions/rules/{pattern}`,
  `PATCH /permissions` for the fallback, and `GET /permissions/matches?pattern=` — which tools a
  pattern covers, answered by the policy's own matcher so the browser holds no second copy of it.
- **A file that cannot be used stops the boot**, with its path, rather than being ignored: an
  ignored file is rules a person wrote that quietly stopped applying.

## Consequences

- Rules made before this version (card answers) were never written down, so there is nothing to
  migrate: the file starts empty and the first change creates it.
- Rules from a profile are shown and not editable here; no profile carries any yet, and when one does
  the screen already says where each rule came from.
- #108 (per-tool checkboxes on the Servers screen) builds on this: unchecking a tool writes a `deny`
  rule through `rulebook.add` ([ADR 24](0024-the-servers-screen-writes-mcp-json.md)).

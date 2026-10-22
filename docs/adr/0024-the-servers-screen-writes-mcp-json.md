# 24. The Servers screen writes `mcp.json`, and a tool that is switched off is not offered

- Status: accepted
- Date: 2026-10-22

## Context

Settings → Servers was a read-only list, and adding a server meant editing `~/.hera/mcp.json` by hand
and restarting ([#108](https://github.com/VoidEUW/hera/issues/108)). Nothing listed which tools a
server had, and there was no way to say *she may not have this one* short of writing a permission rule
by pattern. Her own server was filtered out of the list so the composer would not say "1 server" on a
machine with none, which also meant the screen hid the biggest thing she has.

Two assumptions in the issue did not hold. A `deny` rule did not hide a tool: the turn offered the
whole catalogue and the rule only refused the call, so she could still see, choose and be told no. And
the parsed `McpConfig` is the wrong thing to save: it drops the keys this client does not read
(`alwaysAllow` and a copied block's other annotations — the whole compatibility promise of
[ADR 4](0004-mcp-as-the-tool-layer.md)) and it holds `${VAR}` already expanded, so saving it would
write a real token into a file that was written so as not to contain one.

## Decision

- **The file is edited as the JSON it is.** `hera_tools.config` gains a writer beside the reader:
  `put_server` and `remove_server` change one entry under `mcpServers` and leave every other key and
  entry as written, replace the file atomically, and validate the entry the way the reader will —
  including that every `${VAR}` it names is set — *before* writing. A file nobody can parse is never
  written over.
- **A secret never leaves the server.** The editor is shown an entry with every literal in `env` and
  `headers` masked (`null`); a `${VAR}` is shown as written, because it is the name of a secret and not
  one. A `null` sent back means *keep what is stored*. Keys the form has no field for (other clients'
  keys, the two timeouts) survive a save.
- **A change reconnects only what changed.** `ToolRegistry.with_config` keeps the connected
  `ManagedServer` for every entry whose declaration is unchanged, builds the new and changed ones, and
  hands back the retired ones for the caller to close once nothing is using them. A turn already
  running keeps the registry it started with. The swap shares `permission_rules.LOCK` with the policy
  swap, because both replace `container.registry`.
- **Her own server is a box like the others**, flagged `builtin` — she is a server (ADR 4) — and has no
  edit or remove, because it is not in the file. `GET /servers` includes it; the composer and the health
  card count only what a person added.
- **A tool is switched off by a rule, and a denied tool is not offered.** The checkbox writes `deny` on
  exactly `server__tool` through `hera_core.rulebook` (ADR 23), so it is on the Permissions screen and
  kept across a restart. `Turn._tool_specs` now leaves out a tool the policy denies — for every deny
  rule, not only these — and the call is still refused at dispatch if she names it anyway. Switching one
  back on removes that rule, or, when a wider rule (`fs__*`) still says no, writes an exact `allow` beside
  it, which wins by being more specific.
- **Routes:** `GET /servers`, `PUT` and `DELETE /servers/{name}`, `GET /servers/{name}/config`,
  `GET /servers/{name}/tools`, `PUT /servers/{name}/tools/{tool}`.

## Consequences

- A person can run a server they added without opening a file, and a hand-edited `mcp.json` is still
  the same file and still works.
- Saving a server whose `${VAR}` is not set in Hera's own environment is refused, where the file edited by
  hand would have failed at the next start. The message says which variable.
- A server whose declaration is unchanged is not reconnected by saving another, so one that failed to
  start is retried by editing it (any change), not by saving something else.
- Deny rules now remove tools from what she is offered. A rule written to refuse a tool she should still
  *see* — to teach her by refusal — no longer does that; use `ask` for it.

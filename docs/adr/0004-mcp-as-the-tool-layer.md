# 4. MCP is the tool layer

- Status: accepted
- Date: 2026-08-26

## Context

Tools used to be a hand-written registry: a `TOOLS` dict, a `WRITE_ACTIONS` dict, a
`SILENT_ACTIONS` set, hand-authored OpenAI schemas, and a per-model allow-list checked inside the
agent loop. Adding a tool meant touching the registry, the parser, the segment template and the
frontend renderer. Everything Hera could do, she could only do because it had been wired by hand.

Meanwhile the Model Context Protocol became the way tools are shared between agents, and the
user already runs MCP servers elsewhere.

## Decision

`hera_tools` is an **MCP client**. Tools come from servers declared in `~/.hera/mcp.json`, in the
same `mcpServers` shape Claude Desktop uses, so a configuration block can be copied between them
unchanged. Both stdio and streamable-http transports are supported.

Hera's own capabilities — `emotion`, `remember`, `note`, `skill` — are an **in-process MCP
server**, not a special case beside the client. They travel the same path as a foreign tool:
catalogue, permission check, dispatch, result event.

Tool names are namespaced `server__tool` to keep two servers from colliding. Permission is
decided by `hera_permissions` before dispatch, with an `ask` outcome that surfaces as a
confirmation card — the generalisation of the old confirm-before-write flow, which was the one
piece of the previous tool layer worth keeping.

An unreachable server degrades to a missing tool. It never takes a turn down.

## Consequences

- Adding a capability to Hera is usually adding a server to a JSON file, with no code change.
- Because her own tools are already a server, exposing them to other agents (Claude Code reading
  her memory and skills) is a transport change, not a rewrite. That is planned for v0.3.
- The MCP SDK becomes a load-bearing dependency, and subprocess lifecycle management is now
  Hera's problem: connect lazily, time out per server, survive a crash.
- Tool results are text and structured content per the protocol, which is a narrower contract
  than the ad-hoc Python return values the old registry used. Renderers must handle both.

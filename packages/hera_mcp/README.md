# hera-mcp

The MCP server Hera **is**, as opposed to the ones she can reach.

Four tools on a real `MCPServer` — `emotion`, `remember`, `note` and `skill`, namespaced
`hera__*` once the client mounts them. `hera_tools` is the other half of the pair: it is the
**client**, and it knows nothing about what is on this server.

```python
from hera_mcp import build_builtin_server
from hera_tools import ToolRegistry

registry = ToolRegistry.open(
    builtin=build_builtin_server(skills=SkillLibraryPort(library)),
)
```

The server is mounted under its own `name`, so `"hera"` is written once, here.

## The four

| Tool | Does | Wired in v0.1 |
|---|---|---|
| `hera__emotion(kind, text="")` | Shows a stance as a card beside her answer. `kind` is free text and she may invent one ([ADR 3](../../docs/adr/0003-emotions-as-tool-calls.md)) | yes — it needs nothing |
| `hera__remember(text, scope="global")` | Stores a lasting fact through the `MemoryWriter` port | no — waits for `hera_memories` |
| `hera__note(text, title="")` | Writes a document into the person's notes through `NoteWriter` | no — waits for somewhere to put it |
| `hera__skill(name)` | Loads one skill's full body through `SkillLibrary` | yes |

`emotion` returns one word. The call *is* the record: it is persisted as an event and drawn by
the interface, so anything more would only spend tokens on the way back in.

## Ports, and what "unwired" means

The three tools that touch the rest of the system take **ports** — `MemoryWriter`, `NoteWriter`
and `SkillLibrary` in `hera_mcp.ports`. This package imports no other `hera_*` package, so it
declares what it needs and the application wires it.

Everything is optional, and what is missing **still appears in the catalogue**, answering "not
available in this deployment" as a tool error. That is on purpose: a model that cannot see
`remember` concludes it cannot remember, and tells the person so.

## Descriptions are prompt text

The `description=` on each tool is the only thing that explains it to the model, so it is
written for one: short, imperative, and explicit about when *not* to call. `remember` says not
to store guesses; `skill` says whatever applies has already been given to it. Changing that text
changes her behaviour as surely as changing a mind region does, which is a large part of why
this is a package rather than a module inside the client.

## Why it is its own package

`hera_tools` is about anybody's MCP server: subprocess lifetimes, namespacing, timeouts, retries.
This is about what *Hera* can do. Those change for unrelated reasons, and in v0.3 this is what
gets served over a transport of its own so Claude Code can attach to her — at which point the
only change should be the transport, which is exactly what
[ADR 4](../../docs/adr/0004-mcp-as-the-tool-layer.md) asked for.

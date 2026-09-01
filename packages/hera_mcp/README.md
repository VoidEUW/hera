# hera-mcp

The MCP server Hera **is**, as opposed to the ones she can reach.

Her whole catalogue on a real `MCPServer` — `ask`, `remember`, `forget`, `note`, `skill`,
`search`, the three `scratch_*` and the three `artifact_*`, namespaced `hera__*` once the client
mounts them. `TOOL_NAMES` is the list in code. `hera_tools` is the other half of the pair: it is the
**client**, and it knows nothing about what is on this server.

```python
from hera_mcp import build_builtin_server
from hera_tools import ToolRegistry

registry = ToolRegistry.open(
    builtin=build_builtin_server(skills=SkillLibraryPort(library)),
)
```

The server is mounted under its own `name`, so `"hera"` is written once, here.

## The one that is never run

`hera__ask(question, kind)` is the tool a **person** answers. `hera_chats` recognises it by name
before dispatch — through `ChatsSettings.asking_tools`, filled in from `ASK_TOOL`, because that
package may not import this one — records the question, and closes the turn the way a permission
card closes it. The reply becomes that call's `tool_result`, so nothing on the model's side of the
loop learns a person was in it.

The body here therefore only runs when something drives this server from *outside* a turn, and it
refuses, saying the question was not put to anybody. Returning something that looks like an answer
nobody gave would be worse.

`kind` is a closed set of three — `unsure`, `blocked`, `choice` — in the tool's input schema, so
there is nothing to invent
([ADR 17](../../docs/adr/0017-a-stance-is-a-sentence-and-a-question-stands-alone.md)). It used to
be a word from an editable vocabulary of moods, shared with a `hera__emotion` tool that ADR 17
removed.

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

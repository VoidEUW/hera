# hera-tools

The tool layer: an **MCP client** over the servers declared in `~/.hera/mcp.json`, plus any
in-process server the application hands it — `hera-mcp` carries Hera's own capabilities and is
mounted exactly that way, with no special case here.

Every tool is namespaced `server__tool`, every call is checked by `hera_permissions` before it
runs, and every call comes back as a `ToolResult` — including the ones that were refused,
misnamed, or sent to a server that is not running. See
[ADR 4](../../docs/adr/0004-mcp-as-the-tool-layer.md).

## Installation

Inside this workspace, depend on it by name — uv resolves it to the member:

```toml
dependencies = ["hera-tools"]
```

## Quick start

```python
from hera_mcp import build_builtin_server
from hera_permissions import PermissionSet, Policy
from hera_tools import ToolInvocation, ToolRegistry

registry = ToolRegistry.open(
    policy=Policy(base=PermissionSet.of(allow=["hera__*"], ask=["*"])),
    builtin=build_builtin_server(memories=memories, notes=notes, skills=skills),
)

catalogue = await registry.catalogue()          # every tool every reachable server offers
request_tools = catalogue.as_function_specs()   # ready for hera_providers.ToolSpec(**spec)

result = await registry.dispatch(
    ToolInvocation(call_id="call_1", tool="hera__search", arguments={"query": "qwen"})
)
result.ok       # True
result.text     # what goes back to the model as the TOOL message
```

`ToolRegistry.open()` reads the configuration; `from_config()` takes one already parsed, which
is what tests use. Close it with `await registry.aclose()` — that stops every subprocess.

## Configuration

`~/.hera/mcp.json`, in the Claude-Desktop `mcpServers` shape, so a block copies between the two
unchanged. `command` means stdio, `url` means streamable HTTP, and unknown keys are ignored.

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/notes"]
    },
    "github": {
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": { "Authorization": "Bearer ${GITHUB_TOKEN}" }
    },
    "noisy": { "command": "npx", "args": ["-y", "something"], "enabled": false }
  }
}
```

`${VAR}` and `${VAR:-fallback}` are expanded from the environment. A variable that is not set
is an error rather than an empty string: a blank credential fails minutes later somewhere
unrelated. `enabled`, `timeout_s` and `startup_timeout_s` are ours and optional; everything
else is the protocol's.

A missing file is not an error. Hera with no external servers is a working installation — her
own tools are in-process and do not come from here.

## An in-process server

`from_config(builtin=...)` mounts a server object running inside this process, under its own
`name`, over the SDK's in-memory transport. It is reached by the same client a subprocess is
reached by, listed in the same catalogue, and checked by the same policy — nothing about it is
a special case, which is what makes exposing such a server to other agents in v0.3 a transport
change rather than a rewrite.

Hera's own four tools are one of these, in [`hera-mcp`](../hera_mcp/). This package does not
import it and does not know what is on it; the application puts the two together.

## Failure never reaches the turn

Above `ToolRegistry`, everything is a `ToolResult`:

| `failure` | Means |
|---|---|
| `DENIED` | the policy said no, or said ask and nobody answered |
| `UNKNOWN_TOOL` | no such name — the text lists close ones, and models correct themselves |
| `UNAVAILABLE` | the server would not start, or died |
| `TIMEOUT` | the call exceeded its budget and was abandoned |
| `TOOL_ERROR` | the tool ran and reported an error, which is the protocol working |

`result.text` is always populated, including on failure, because it becomes the `TOOL` message
of the next request. Feed it back and the model tries something else. This is the same
reasoning as `ToolCallReady.parse_error` in `hera_providers`: one bad call must not end a turn.

Below that line things raise — `ServerUnavailable`, `ToolTimeout` — so `ManagedServer` is
honest when used on its own. `InvalidToolConfig` and `InvalidToolName` are different in kind:
they mean a person wrote something wrong, and they surface at boot where that person can read
them.

## Lifecycle

Servers connect on first use and stay connected. Each one owns a **worker task** that holds its
client for as long as it lives, because the SDK's client owns an anyio task group and those are
task-affine — opened in a web request and closed at shutdown is opened and closed in two
different tasks, which unwinds into "cancel scope in a different task" instead of a clean exit.
Calls are handed to that worker and run as children of it, so parallel tool calls to one server
stay parallel.

A server that fails to start is left alone for `retry_after_s` and then tried again. A server
that *dies mid-conversation* is noticed too: a stdio process that exits leaves the client
looking healthy while every later call fails with "Connection closed", so that is detected and
the connection retired, and the next call starts a fresh process.

## What does **not** belong here

Policy (this package asks `hera_permissions`), prompts, chats, and any knowledge of what a
particular tool means. Deciding *which* skill applies is `hera_skillsets`
([ADR 5](../../docs/adr/0005-deterministic-skill-routing.md)) — the `hera__skill` tool here is
the door left open for a model that works it out mid-task, and nothing depends on that
happening.

# Configuration

Hera is configured in two layers: environment variables, read once at startup, and
`~/.hera/config.toml`, which a running Hera reads and writes and which wins once it exists.

## Where your data lives

Everything Hera owns lives under `~/.hera/`. Set `HERA_HOME` to move the whole thing elsewhere.

| Path | Contents |
|---|---|
| `hera.sqlite3` | chats, messages, projects, profiles, permissions |
| `mind/` | a real git repository, one file per mind region |
| `memories/<key>.md` | what Hera knows about you, one file per memory |
| `skills/<name>/SKILL.md` | skill packages |
| `chats/<id>/scratch/` | one conversation's working files, deleted with the chat |
| `chats/<id>/artifacts/` | one conversation's published files, deleted with the chat |
| `mcp.json` | external MCP servers |
| `config.toml` | model endpoints and other settings, written by the interface |

## Server settings

Read from environment variables, prefixed `HERA_`, at process start:

| Variable | Default | Purpose |
|---|---|---|
| `HERA_HOME` | `~/.hera` | Where all data is stored |
| `HERA_HOST` | `127.0.0.1` | Interface to bind to. Loopback by default — binding to every interface is a decision you make on purpose |
| `HERA_PORT` | `8756` | Port to listen on |

There is no login and no multi-user support. Hera is one person's server on one person's
machine. Do not set `HERA_HOST` to `0.0.0.0` unless the machine is otherwise unreachable from
outside your network.

## Model endpoint

Hera talks to any OpenAI-compatible endpoint — LM Studio, vLLM, llama.cpp, or similar — and is
tuned specifically for **Qwen3.6-35B**. Any endpoint with working native tool calling should
work.

The endpoint can be set two ways:

**Environment variables**, read once, only to seed `config.toml` the first time it is written:

| Variable | Default | Purpose |
|---|---|---|
| `HERA_PROVIDER_BASE_URL` | `http://localhost:1234/v1` | The endpoint's base URL |
| `HERA_PROVIDER_MODEL` | `qwen3.6-35b` | The model name, as the endpoint expects it |
| `HERA_PROVIDER_API_KEY` | empty | Empty for a local server, which is the intended setup |
| `HERA_PROVIDER_EMBEDDING_MODEL` | empty | Optional. Empty means retrieval falls back to keyword search |
| `HERA_PROVIDER_TIMEOUT_S` | `600` | How long the endpoint may go silent before a turn gives up. Not how long a turn may take — a streamed answer resets this on every token, so it really only bounds loading the model and prefilling the prompt |
| `HERA_PROVIDER_CONNECT_TIMEOUT_S` | `5` | How long to wait for the endpoint to accept a connection at all |

**Settings → Models**, in the interface, once Hera is running. This is the normal way to
change the endpoint after first install — it edits `config.toml` directly, and once that file
exists, the environment variables above no longer have any effect.

You can save more than one endpoint and switch between them; one is marked active at a time.

## `config.toml`

Written by the interface, safe to edit by hand. A fresh install has none — it's generated from
the environment variables above the first time it's written.

```toml
active_provider = "local"

[[providers]]
name = "local"
base_url = "http://localhost:1234/v1"
model = "qwen3.6-35b"
timezone = "Europe/Berlin"
```

`timezone` is an IANA name (`Europe/Berlin`), not a UTC offset — an offset is wrong twice a
year. Empty means the prompt carries UTC alone. Set it from Settings, or by hand.

## `mcp.json`

External MCP servers, in the Claude-Desktop `mcpServers` shape — a block copies between the
two files unchanged. `command` means the server runs as a subprocess over stdio; `url` means
streamable HTTP.

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

`${VAR}` and `${VAR:-fallback}` are expanded from the environment; a variable that isn't set
is an error rather than a blank credential. `enabled`, `timeout_s` and `startup_timeout_s` are
optional. A missing file is not an error — Hera with no external servers is a working
installation; her own tools are built in and don't come from here.

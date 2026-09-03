# Source Installation

Run Hera directly from a checkout, with `uv` and Node. No container.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Node 20 or newer, to build the web interface
- A local OpenAI-compatible model endpoint (LM Studio, vLLM, llama.cpp) serving
  **Qwen3.6-35B**. Any endpoint with working native tool calling should work too.

## Install

```bash
git clone https://github.com/VoidEUW/hera.git
cd hera
uv sync --all-packages
```

This installs the Python application and every package in the workspace.

## Build the web interface

The server serves the interface as static files. They have to be built once:

```bash
cd apps/core/web
npm ci
npm run build
cd ../../..
```

## Run

```bash
uv run hera serve
```

Open `http://localhost:8756`.

The server binds to `127.0.0.1` only. There is no login and no multi-user support. Do not
expose this to a public network as it stands.

## Where your data lives

Everything Hera owns lives under `~/.hera/`. Set `HERA_HOME` to change the location. See
**Configuration** for the full list of settings and environment variables.

## Connecting a model

Hera talks to an OpenAI-compatible endpoint. Point it at the endpoint through the Settings
screen after first launch, or set it up front with `HERA_PROVIDER_BASE_URL` and
`HERA_PROVIDER_MODEL` before the first run — see **Configuration**.

## Updating

```bash
git pull
uv sync --all-packages
cd apps/core/web && npm ci && npm run build && cd ../../..
```

Rebuild the web interface after every update — the server serves whatever was last built into
`apps/core/src/hera_core/static/`.

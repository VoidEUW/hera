# Hera

A self-hosted agentic chat space. One server on your own machine, reachable from your desk and
from your phone, talking to a **local** model over an OpenAI-compatible endpoint.

Hera is not a thin chat window. She keeps a **git-versioned mind** you can read and edit, learns
from **experience training** you feed her, reflects on her own conversations (**dreaming**), and
speaks with **emotion cards** next to her prose. Her tools come from **MCP servers** and her
know-how from **`SKILL.md` skills**, so both are portable to and from the rest of the ecosystem.

> Status: **v0.1 is complete and the spine runs end to end** — a message typed into the browser
> reaches a model through the skill router, the mind and the turn orchestrator, and comes back as
> events the interface renders. See [CHANGELOG.md](CHANGELOG.md) for what is in it and what is
> deliberately not, [ARCHITECTURE.md](ARCHITECTURE.md) for the shape, and [docs/adr/](docs/adr/)
> for why. Memory, retrieval and dreaming are v0.2.

## What makes it different

| | |
|---|---|
| **Emotion cards** | The model calls `hera__emotion(kind, text)` and the answer carries a stance card — agreement, doubt, a joke — beside the prose. The vocabulary is a starting point, not a cage: invented kinds render too. |
| **A mind you can read** | Identity, role, character, tone, safety and workflow each live as a Markdown file in a real git repository under `~/.hera/mind/`. Editing one is a commit. Nothing changes without your approval. |
| **Dreaming** | Hera re-reads her own conversations and proposes changes to her mind and memory. Every proposal is a card you accept, reject or revert. Rejections come back as counter-examples in the next run. |
| **Experience training** | Drop in documents — task plus model answer — and they become material she distils lessons from, never facts about you. |
| **MCP-native tools** | `~/.hera/mcp.json` uses the same shape as Claude Desktop. Point her at a server and its tools are hers. |
| **Deterministic skills** | Skills are `SKILL.md` packages, but *Hera does not have to notice them*: a server-side router pins, resolves `/slash` invocations and retrieves by relevance before the model ever sees the turn. |

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node 20+ (for the web app)
- A local OpenAI-compatible endpoint serving **Qwen3.6-35B** — LM Studio, vLLM or llama.cpp.
  Hera is tuned for that model specifically; anything with working native tool calling should
  behave.

## Quick start

```bash
git clone https://github.com/VoidEUW/hera.git
cd hera
uv sync --all-packages
uv run hera serve                 # http://localhost:8000
```

The first visit asks you to set a password. Everything Hera owns lives under `~/.hera/`
(`HERA_HOME` overrides it): the database, the `mind/` git repository, your `skills/`, and
`mcp.json`.

## Development

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run coverage run -m pytest && uv run coverage report
```

Everything is one workspace: a single `uv sync` and every library is editable in place. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Layout

```
packages/     the libraries, each with one job and no upward imports
apps/core     hera-core — FastAPI (/api/v1 JSON + SSE) and, under web/, the
              SvelteKit interface it serves: desktop-shaped, installable as a PWA
docs/adr      why the structure looks like this
```

## Licence

MIT.

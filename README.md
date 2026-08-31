# Hera

A self-hosted agentic chat space. One server on your own machine, reachable from your desk and
from your phone, talking to a **local** model over an OpenAI-compatible endpoint.

Hera is not a thin chat window. She keeps a **git-versioned mind** you can read and edit,
**remembers** what matters about you in files you can take elsewhere, **publishes** what she makes
as real artifacts, and speaks with **emotion cards** next to her prose. Her tools come from **MCP
servers** and her know-how from **`SKILL.md` skills**, so both are portable to and from the rest of
the ecosystem.

> Status: **v0.2 is in progress and everything below except dreaming is built.** v0.1 made the
> spine run end to end — a message typed into the browser reaches a model through the skill router,
> the mind and the turn orchestrator, and comes back as events the interface renders. v0.2 makes it
> *accumulate*: projects, a scratchpad, artifacts, and memory. **Dreaming and experience training
> moved to v0.3** so the four under them can be stabilised first
> ([docs/versions/v0.3.0.md](docs/versions/v0.3.0.md)).
>
> [CHANGELOG.md](CHANGELOG.md) for what is in it and what is deliberately not,
> [ARCHITECTURE.md](ARCHITECTURE.md) for the shape, [docs/adr/](docs/adr/) for why.

## What makes it different

| | |
|---|---|
| **Emotion cards** | The model calls `hera__emotion(kind, text)` and the answer carries a stance card — agreement, doubt, a joke — beside the prose. The vocabulary is a starting point, not a cage: invented kinds render too. |
| **A mind you can read** | Identity, role, character, tone, safety and workflow each live as a Markdown file in a real git repository under `~/.hera/mind/`. Editing one is a commit. Nothing changes without your approval. |
| **Memory you can take with you** | One markdown file per memory in `~/.hera/memories/`, and **every one that is switched on is in her prompt, whole** — no retrieval, so a memory that was stored cannot silently fail to arrive. The cost is space, so the space is on screen: a bar, and a switch that keeps a memory without paying for it. **Export `MEMORY.md`** and take the lot somewhere else. |
| **Artifacts** | A page, a chart, a document, published as a *file* rather than left in a code fence for you to copy out — with a panel beside the conversation, a download, and an `edit` that changes one line instead of re-emitting 40 KB. |
| **A scratchpad per conversation** | Somewhere to leave herself a plan between turns. Hers, unread, and thrown away with the chat. |
| **Dreaming** *(v0.3)* | Hera re-reads her own conversations and proposes changes to her mind and memory. Every proposal is a card you accept, reject or revert. Rejections come back as counter-examples in the next run. Listed on the settings screen and disabled until then, because a feature you can see coming is a promise and one you cannot is a surprise. |
| **Experience training** *(v0.3)* | Drop in documents — task plus model answer — and they become material she distils lessons from, never facts about you. |
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
uv run hera serve                 # http://localhost:8756
```

It binds to `127.0.0.1` and there is no login: Hera is one person's server on one person's
machine, and every route resolves an owner through a single seam so that adding one later is a
change in one function rather than in every query. **Do not put this on a public interface as it
stands.**

Everything Hera owns lives under `~/.hera/` (`HERA_HOME` overrides it):

| | |
|---|---|
| `hera.sqlite3` | chats, messages, projects, profiles, permissions |
| `mind/` | a real git repository, one file per mind region |
| `memories/<key>.md` | what she knows about you — one file each, and the filename is the key |
| `skills/<name>/SKILL.md` | skill packages |
| `chats/<id>/` | one conversation's `scratch/` and `artifacts/` |
| `mcp.json` · `config.toml` | MCP servers, and the model endpoints the interface writes |

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
packages/          the libraries, each with one job and no upward imports
apps/core          hera-core — FastAPI (/api/v1 JSON + SSE) and, under web/, the
                   SvelteKit interface it serves: desktop-shaped, installable as a PWA
docs/adr/          why the structure looks like this
docs/versions/     what each version is for, written before the work rather than after
docs/status.md     where the rebuild stands right now
```

## Licence

MIT.

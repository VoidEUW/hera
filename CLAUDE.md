# CLAUDE.md — Hera

A map of this repository, not a changelog. Keep it short: the previous version of this file grew
to 98 KB of accumulated history and stopped being readable. It is archived as
`docs/prototype.md` — useful for *why* decisions were made, wrong about everything structural.

Hera is a self-hosted agentic chat space: a uv workspace of small libraries, a FastAPI
application, and a SvelteKit interface, talking to a local Qwen3.6-35B over an
OpenAI-compatible endpoint.

## Read first

- `docs/status.md` — where the rebuild stands, what is settled, what is next. Start here
- `docs/versions/` — what each version is for and in what order it lands. **v0.2.0 is tagged**;
  v0.2.1 is the polish pass and v0.3.0 the widening one. Read the one you are working on before
  touching its packages
- `ARCHITECTURE.md` — the packages, the layering rule, the shape of a turn
- `docs/adr/` — why the structure looks like this; read 2 (Qwen only), 5 (deterministic skill
  routing) and 17 (a stance is a sentence) before changing model-facing behaviour. 17 supersedes
  3, and 3 is worth reading anyway for the rule that outlived it
- `docs/tooling.md` — what she should be able to reach for and cannot. Notes, not decisions;
  read it before adding a tool, and read § 1 before concluding she has no search *on purpose*
- `CONTRIBUTING.md` — setup, the check loop, branching
- `docs/README.md` — what the prototype document is still good for, and what it is wrong about

## Commands

```bash
uv sync --all-packages
uv run ruff check . && uv run ruff format --check .
uv run mypy                                         # strict
uv run coverage run -m pytest && uv run coverage report
uv run pytest -m e2e                                # Playwright against FakeProvider
uv run hera serve
```

`-m "not e2e and not live"` is the fast loop. `live` marks anything that needs a real model
endpoint; it never runs in CI.

## Rules that are not negotiable

**Imports point downwards.** The table in `ARCHITECTURE.md` is the authority, and
`tests/test_layering.py` enforces it. `hera_storage`, `hera_prompts`, `hera_providers`,
`hera_permissions` and `hera_mcp` import no other `hera_*` package; the first two contain no
domain concept at all and must stay liftable into an unrelated project.

**Two MCP packages, and the difference matters.** `hera_mcp` is the server she *is* —
`hera__ask`, `hera__remember`, `hera__forget`, `hera__note`, `hera__skill`, `hera__search`, the
three `hera__scratch_*`, the three `hera__artifact_*`, and the ports they take. `hera__ask` is the
one that is never *run*:
`hera_chats` recognises it by name (`ChatsSettings.asking_tools`, filled in by the application)
and suspends the turn the way a permission card does, so a person's reply becomes that call's
result. `hera_tools` is the client she *has*, and it does not know the other exists: it mounts
whatever in-process server the application hands it, under that server's own name. Her tool
descriptions are prompt text; edit them in `hera_mcp` and her behaviour changes.

**Two directories per chat, and they are not one directory with a flag.** `scratch/` is hers and
nobody reads it, which is what lets her think out loud in it; `artifacts/` is what she publishes,
and a person browses it. Same guard, same cleanup, opposite promises — `hera_core.chat_files` owns
both adapters so the name check exists once.

**A tool learns which chat it is in from `_meta`, never from an argument** — [ADR 12](docs/adr/0012-a-chat-has-a-scratchpad.md).
The model chooses arguments, so a `chat_id` field is one it would invent; a `ctx: Context`
parameter is kept out of the tool's schema by the SDK, so there is nothing to invent. `hera_tools`
carries an opaque mapping and does not read it, `hera_mcp.CHAT_ID_META` is where the key is
written, and `ChatsSettings.chat_meta_key` is how it travels — the same arrangement as
`asking_tools`, because the two packages may not import each other. A `contextvars.ContextVar`
does **not** work here and does not fail either: every call runs in a worker task created when the
server connected, so it reads back empty.

**One event union.** `hera_providers` defines what a model can emit; everything above consumes
it. If you are writing a parser for model output outside that package, something is wrong — the
answer is almost always a tool call.

**No second parser in the browser.** The frontend renders event variants it is given. This is
the single largest source of bugs in the previous version and it is designed out. Typesetting
her prose as Markdown and TeX is not that parser and may not become one — it draws text as what
it is and reads no meaning back out of it. See ADR 11.

**The server render is authoritative.** The client replaces its optimistic view with the
persisted event list at `done`.

**Skill selection is code.** Never build a feature that depends on the model noticing a skill is
relevant; the target model does not. See ADR 5.

**English everywhere** — code, comments, commits, prompts, stored content, UI strings. UI text
goes through i18n so a German locale can be added later.

**Tables** carry a package-prefixed `__tablename__`; cross-package references are bare `UUID`
columns, never `ForeignKey`; migrations live in `apps/core`.

## What lives in `~/.hera`

| | |
|---|---|
| `hera.sqlite3` | everything relational |
| `mind/` | a real git repository, one file per mind region |
| `memories/<key>.md` | what she knows about you, one markdown file each. The filename is the key; every enabled one is in the prompt, under a token ceiling ([ADR 16](docs/adr/0016-a-memory-is-a-file-and-all-of-them-are-in-the-prompt.md)) |
| `skills/<name>/SKILL.md` | skill packages |
| `chats/<id>/scratch/` | her working files for one conversation. A cache, not something you keep — deleting the chat deletes it |
| `chats/<id>/artifacts/` | what she publishes there: the filename is the identity, the extension is the kind. Goes with the chat too ([ADR 13](docs/adr/0013-an-artifact-is-a-file-she-publishes.md)) |
| `mcp.json` | MCP servers, in the Claude-Desktop `mcpServers` shape |
| `config.toml` | registered model endpoints, written by the interface |
| `trusted.json` | **where trusted skills are recorded** — optional |

`trusted.json` is the only thing that can put a *verified* mark on a skill, because a skill
vouching for itself has vouched for nothing. It maps an identifier to the SHA-256 of the content
you accepted:

```json
{ "skills": { "tdd": "9f2c…" } }
```

`hera_skillsets` digests each `SKILL.md` (it is already holding the bytes); `hera_core.trust`
decides what the digest means, because the same file will cover MCP servers and neither package
may import the other. Three verdicts: **verified**, **modified** — listed but the content has
changed since, which is worth saying loudly — and **unknown**, which is the ordinary state and
not a complaint. No file means nothing is verified; the signed registry this is a seam for does
not exist yet.

**Every memory is in the prompt, and that is the decision** — [ADR 16](docs/adr/0016-a-memory-is-a-file-and-all-of-them-are-in-the-prompt.md).
There is no retrieval and no ranking, because a memory that was stored and did not arrive looks
exactly like one that was never stored, and nobody on either side can tell which happened. The cost
is space, so the space is the feature: a ceiling in tokens, a bar on Settings → Memory, and
switching one off keeps the file and gives the space back. Two tools, and what is missing from them
is the design — nothing lists memories (they are already in her prompt) and `hera__forget` does not
delete (**the only thing that unlinks one is a person on the settings screen**).

**A stance is a sentence, and a question stands on its own** — [ADR 17](docs/adr/0017-a-stance-is-a-sentence-and-a-question-stands-alone.md),
which supersedes 3. `hera__emotion` and the whole stance vocabulary are **gone**: driven against a
real endpoint she reached for a stance rarely and close to arbitrarily, because several of the
fourteen fired on the same occasion and one of them had become a tool. What replaces it is nothing
— *I think this is wrong, and here is why* is the same information, in the place a reader is
already looking. `tone` and `character` are the mind regions that govern it. An
`~/.hera/emotions.json` left over from an older install is **ignored, never deleted**.

`hera__ask` was the thing coupled to it, so it was detached **first**: `kind` is now a closed
`Literal` of `unsure · blocked · choice` — the three occasions the `uncertainty` region already
describes — in the tool's own schema, where the model cannot invent one and the card does not have
to look one up. `AnswerRequired.kind` stays a plain `str`, because `hera_chats` may not learn her
tool's schema and a turn persisted before the set was closed still has to load.

Which language she answers in is the `language` mind region, edited on Settings → Mind like every
other behaviour.

## State of the build

See `docs/status.md` — kept there so this file stays a map rather than turning back into a
changelog.

Commit and push only when asked. Branch first — `main` is protected.

# Changelog

Notable changes to Hera, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**A version here is a tag, not a branch.** Nothing ships off `main`; `v1.2.3` releases the
application and `hera-skillsets-v0.1.0` releases one library so another project can pin it
without pinning Hera. `release.yml` refuses a tag whose version disagrees with the
`pyproject.toml` it belongs to, and `hera_core.__version__` reads the installed distribution —
so the number in this file, on the tag, and in the interface cannot drift apart. See
[CONTRIBUTING.md](CONTRIBUTING.md) and [ADR 8](docs/adr/0008-github-flow-and-required-checks.md).

## [0.2.0] — unreleased

**The deepening pass: what makes her accumulate.** v0.1.0 runs a turn end to end and forgets it
happened. This version adds the four things that change: projects you can actually make, artifacts
she can produce and revise, memory across conversations, and dreaming — she re-reads her own chats
and proposes changes you accept or reject.

The order is **organise → produce → make room → remember → reflect**, and it is not aesthetic:
artifacts and memory both want a panel beside the conversation, so the interface pass sits between
them; dreaming reads memories and proposes to the mind, so it cannot come earlier.

Planned, in [docs/versions/v0.2.0.md](docs/versions/v0.2.0.md) — the reasoning lives there, and this
section fills in as milestones land.

### Added

- **Projects you can actually make.** The server half shipped in 0.1.0 and nothing could reach it:
  `Project` had instructions, pinned skills and a default profile, and no screen created one. There
  is now a **＋** on the rail's `PROJECTS` heading, a `⋯` on every project row (open · rename ·
  remove), and a project screen at `/project/<id>` carrying the instructions, the pinned skills,
  the default profile and its chats. Not a Settings tab — Settings is *how she works*, a project is
  the work.
- **A chat can be moved between projects**, from its own `⋯`. `PATCH /chats/{id}` grew a
  `project_id`, and it is the one field on that endpoint where `null` means *loose* rather than
  *leave it* — the route reads `model_fields_set` rather than putting a tri-state on the wire.
- **A project has a colour**, from the palette rather than from a colour wheel: a token name, so
  each theme resolves it to its own value and a hue picked in the dark is still legible on vellum.
- **A seam for agent selection.** `Project.default_agent_id` is a column nothing reads, drawn as a
  disabled control saying v0.3 — the same call Settings → Dreaming makes.
- **One selector, and one popup.** `Select.svelte` replaces every dropdown in the application. The
  trigger is the composer's pill — the shape that was already right — and the popup is the *skill
  picker's*: raised surface, hairline, large radius, the same shadow, a brass check on the chosen
  row. Before this the composer's two pills were a native `<select>` wearing `appearance: none`,
  which gave back the frame and left the list the platform's, and every other selector was bare
  native. A person should not be able to tell from the way a list looks whether it came from a
  dialog, a dropdown or a `⋯` menu — the rail's menus share the frame too. Keyboard throughout:
  arrows walk it, Home and End jump, Escape closes and hands focus back.

### Fixed

- **`PATCH /projects/{id}` could not clear a default profile.** The route tested
  `default_profile_id is not None`, which is right for every other field on that body and wrong for
  this one: choosing the screen's empty option was a no-op, and the control snapped back on the
  next load with nothing to explain it.

### Still to come in this version

- **Artifacts** — a diagram, a document, a workflow chart as an object with an identity and
  versions, not prose in a code fence. A tool call like everything else (ADR 11 forbids the browser
  discovering one), rendered as Mermaid, Markdown, code or sandboxed HTML.
- **Skill resources become readable.** `hera_skillsets` already tells the model a skill has files
  beside it; `hera__read_resource` makes that sentence true, which is what Anthropic's
  reference-heavy skills need. Script-running skills report honestly instead — running code is
  `hera_sandbox`, and it is not this version.
- **`hera_memories`.** Retrieval with per-tier caps, write-dedup, hit counts. `hera__remember` stops
  answering "not available in this deployment", and the embedder seam v0.1 left open closes.
- **`hera_promptevo`.** Dreaming, proposing to evolvable mind regions and to memory. Every proposal
  is a card; nothing is applied automatically, and a rejection comes back as a counter-example.
- **An interface pass** — one drawer the three new panels share, the `⌘K` command palette, and the
  rail and transcript rework the new features need.

## [0.1.0] — unreleased

**The first release: the spine runs end to end.** A message typed into the browser reaches a
model through the skill router, the mind and the turn orchestrator, and comes back as
Server-Sent Events the interface renders — with tools, permissions and her own stance along the
way. Hera was rebuilt from an empty repository for this; the previous version is retired to
[docs/prototype.md](docs/prototype.md) and is wrong about everything structural.

### The shape of it

A uv-workspace monorepo: ten small libraries under `packages/`, one application, `hera-core` at
`apps/core/`, with the SvelteKit interface under `web/` built into the directory the API serves.
Eleven decision records in [docs/adr/](docs/adr/) say why. The layering rule — imports point
downwards, `hera_storage` and `hera_prompts` know no domain concept at all — is enforced by
`tests/test_layering.py` rather than by good intentions.

### Added

**The model boundary.** `hera_providers` defines one event union covering everything a model can
emit; everything above consumes it and nothing above parses text. `QwenAdapter` reads
`reasoning_content` where the server offers it and lifts `<think>…</think>` out of the content
stream where it does not. A malformed tool call arrives as `parse_error` on the event rather than
as an exception, so one bad call does not discard the calls beside it. `FakeProvider` means every
layer above is testable with no model running.

**Tools are MCP servers.** `hera_tools` is the client — subprocess lifetimes, namespacing,
timeouts, retries — and reads `~/.hera/mcp.json` in the Claude-Desktop shape. Verified against a
real gateway, not only against a stub.

**Her own capabilities are an MCP server like any other.** `hera_mcp` offers `hera__emotion`,
`hera__remember`, `hera__note`, `hera__skill` and `hera__search`, mounted through the same client,
listed in the same catalogue and checked by the same permission policy. `remember` and `note`
wait for v0.2 and say so to the model rather than vanishing from the catalogue.

**Web search, over DuckDuckGo.** A `Searcher` port in `hera_mcp` and an adapter in the
application, so no library knows which engine a person's questions are sent to. No API key, so a
fresh install can search — which was the point: a model with no way to look something up does not
answer "I cannot check that", it guesses fluently.

**Emotions are tool calls** (ADR 3). `hera__emotion(kind, text)` renders as a card inline where
she called it. `kind` is free text and an unknown one renders generically. Her vocabulary is
data — `~/.hera/emotions.json`, edited on Settings → Emotions — rendered into the prompt per turn
*and* used to colour the card, so the two cannot disagree.

**Skills are `SKILL.md` packages, selected by code** (ADR 5). Pinned → `/slash` → retrieved by
keyword overlap, all server-side, before the model sees the turn. Every selection says which of
the three it was, because "she always has this" and "she went and found this" are different
facts. Skills can be pinned per conversation from the composer. Usage is counted.

**Trust marks.** `~/.hera/trusted.json` maps a skill id to the SHA-256 you accepted — the only
thing that can put a *verified* mark on a skill, because a skill vouching for itself has vouched
for nothing. Three verdicts: verified, **modified**, and unknown, which is the ordinary state and
not a complaint.

**A git-backed mind.** `hera_profiles` keeps twelve mind regions as one file each in a real git
repository at `~/.hera/mind/`, with owner-fixed and evolvable tiers, behaviour traits, and
profiles that override regions. Which language she answers in is one of those regions, not a
setting.

**Permissions.** `hera_permissions` resolves allow · deny · ask by pattern and profile. A
confirmation card suspends the turn, waits for a person, and resumes with their answer;
"always allow" writes a rule. Her own tools are allowed by default, and the reasoning for that is
written down where the rule is.

**Chats, projects, and a persisted event stream.** `hera_chats` stores a turn as the events it
was made of, coalesced, and rebuilds the wire conversation from them — one assistant turn becomes
several messages so a `tool_call_id` always has an answer. Editing a question and asking again are
the same request.

**A JSON and SSE API, and the interface it serves** (ADR 6). FastAPI at `/api/v1`, one origin, no
CORS. The client throws away everything it drew optimistically when `done` arrives and re-renders
from the persisted message, so a reload cannot show something different from what was watched.

**The interface.** The rail with projects disclosing their chats, the start screen, settings as a
modal, the activity gutter with a reason on every skill, emotion cards inline, permission cards,
dark and light. Her prose is *typeset* as Markdown and TeX (ADR 11) — drawn as what it is, with
no meaning read back out of it.

**Attachments, including pictures.** Files are read in the browser and sent as a field, never
pasted into the message text — which is what lets the bubble draw a chip without hunting for a
fence in the prose. 2 MB a text file, 12 MB a picture, PNG/JPEG/WebP/GIF. A picture travels as a
content part beside the words; a message without one stays a plain string on the wire.

**Model endpoints are configuration you can edit.** Several may be registered in
`~/.hera/config.toml`, one is active, and switching takes effect on the next turn without a
restart. The API key is write-only. Probing an endpoint is a normal answer rather than a 500,
because "nothing is listening on that port" is the commonest thing to be wrong on a fresh install.

**Where your data is.** Everything lives in `~/.hera` and nothing in it is a format you cannot
open in an editor: `hera.sqlite3`, `mind/` as a git repository, `skills/<name>/SKILL.md`,
`mcp.json`, `config.toml`, and optionally `trusted.json` and `emotions.json`.

### Changed

- **The palette is parchment, laurel and brass.** The first pass was a warm cream ground under
  white cards, which is the arrangement people recognise from across a room before they have read
  a word. The ground is gold now — aged vellum by day, gold-brown black by night — with laurel
  green for live state and brass leading. `pomegranate` is a crimson rather than a coral, which is
  both more accurate to the fruit she is named for and further from every other warm mid-red.
  See [docs/frontend.md](docs/frontend.md) for the reasoning, which matters more than the hexes.
- **The activity gutter is in event order.** Reasoning comes in blocks, split wherever something
  visible happened, so a turn that thinks, calls a tool and thinks again reads downwards instead
  of folding its second thought into a row above the call that caused it. A block still being
  written previews its own last three lines and collapses to a single row when it closes.
- **Her own tools name what they did**, foreign ones name where they came from: *skill
  rust-best-practices* and *search kerberos ticket lifetime*, against *called **Docker** mcp
  find*. Search, notes, memory and skills each get their own mark in the gutter.
- **New chat opens the start screen** rather than creating an empty transcript, so an abandoned
  one leaves no empty row in the rail.
- `hera_mcp` was split out of `hera_tools`. The client no longer knows the server she is: it
  mounts whatever in-process server the application hands it, under that server's own name.

### Fixed

- A block of reasoning could not be opened while she was still writing it — its key changed with
  every fragment that arrived, so the row was rebuilt several times a second and forgot it had
  been opened.
- A long search query pushed the activity row wider than the reading column and took the duration
  off the end with it.
- The composer's model and profile dropdowns rendered as native controls in a bar of hand-drawn
  ones.
- The context pill on the start screen opened Settings instead of the skill picker.
- Marks in the activity gutter sat below their own text, and the hairline was drawn through the
  three newest of them.

### Known gaps

Deliberate, and listed so a missing feature and a broken one do not look alike:

- **No memory.** `hera_memories`, retrieval and the embedder are v0.2; `hera__remember` and
  `hera__note` are wired to nothing and say so. Skill retrieval falls back to keyword overlap,
  which ADR 5 names as supported.
- **No `hera__fetch`.** She can find a page and cannot read it.
- **No PDFs.** Scoped for v0.1.0 and not built; the composer refuses them with a reason.
- **No command palette.** `⌘K` opens Settings for now.
- **No mobile sheet.** The interface is desktop-shaped; the rail steps aside below 780 px.
- **Single user**, behind a multi-user-ready seam: `Depends(current_user)` on every route and an
  `owner_id` on every row.

[docs/tooling.md](docs/tooling.md) argues for the rest of the tool surface — a per-chat
scratchpad, an emotion that can ask a question back, artifacts — as notes rather than decisions.

[0.2.0]: https://github.com/VoidEUW/hera/releases/tag/v0.2.0
[0.1.0]: https://github.com/VoidEUW/hera/releases/tag/v0.1.0

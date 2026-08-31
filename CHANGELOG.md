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

## [0.2.0] — 2026-08-31

**The deepening pass: what makes her accumulate.** v0.1.0 ran a turn end to end and forgot it
happened. This version adds the four things that change: projects you can file work under, a
scratchpad she thinks on between turns, artifacts she publishes as real files, and memory that
survives a conversation.

The order was **organise → produce → remember**, and it was not aesthetic: projects were nearly
built already and everything else gets filed under them; artifacts needed somewhere to put the bytes
before memory could reuse the panel beside them.

**Two of the five planned milestones moved before the tag**, both deliberately and both written
down rather than dropped. *Dreaming and experience training* are now
[v0.3.0](docs/versions/v0.3.0.md) — the four under it want to be stable before anything proposes
changes to them, and it is the only one that costs nothing to defer, because every dependency points
into it and none point out. *The redesign pass* is now [v0.2.1](docs/versions/v0.2.1.md) with the
`⌘K` palette, hotkeys and `hera__read_resource`: the one part of it anything depended on — the
drawer — was built early with artifacts, and what is left is polish, which is what a patch release
is for.

Planned in [docs/versions/v0.2.0.md](docs/versions/v0.2.0.md); the reasoning lives there.

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
- **She can ask you something and wait for the answer.** `hera__ask(question, kind)` stops the
  turn, draws a card with a reply field where she asked, and resumes the *same* assistant message
  with what you typed as the result of her own call — so nothing on the model's side of the loop
  learns a person was in it. Deliberately the permission card's machinery rather than a second
  suspension beside it ([docs/tooling.md](docs/tooling.md) § 4): a new close reason
  (`awaiting_answer`), two event variants, and `POST /chats/{id}/answers`. `hera_chats` does not
  know the tool exists — it suspends on a name it is given.
- **Two mind regions, and the model asked for both.** Reading its own prompt it reported two gaps
  in the same shape: nothing said what to do when it is **unsure** of an answer, and nothing said
  what to do when it notices mid-task that it is **on the wrong track**. Both are behaviours it
  has anyway, and a default that is nowhere in the mind is one nobody can find and nobody can
  change. `uncertainty` and `correction` join `approach`, which became a group to hold the three.
  Evolvable, because the useful version of *when should I ask?* is learned from conversations that
  went badly. `uncertainty` and `hera__ask` shipped together: telling her to ask, with no way to,
  produces a model that announces its confusion and guesses anyway.
- **She knows what day it is.** The date and time go into every prompt — UTC always, plus the
  person's local time when a zone is set on the profile menu. A model that does not know the date
  answers "what is current" from its training data, confidently and a year late, and nothing on
  screen tells that apart from an answer that is merely wrong. Implicit rather than a tool: a
  `what_time_is_it` call would spend a round trip to learn something free, and would only be made
  by a model that already suspected it needed to. An IANA name rather than an offset, because an
  offset is wrong twice a year.
- **A scratchpad, per conversation.** Somewhere to put a plan, an intermediate result, a list of
  what has been checked so far — `hera__scratch_write`, `hera__scratch_read` and
  `hera__scratch_list` over `~/.hera/chats/<chat id>/scratch/`. It is hers rather than something
  you read, and the win is the *next* turn: she picks up where she left off without the whole
  thing being replayed through the context window. `hera__note` keeps the description it has and
  stops being reached for as working memory, which is what it was actually being used as. Deleting
  a chat deletes the directory, because a cache that outlives what it belongs to is litter.
- **She can make you a thing.** `hera__artifact_create`, `hera__artifact_edit` and
  `hera__artifact_read` over `~/.hera/chats/<chat id>/artifacts/` — a page, a document, a chart,
  a small program, published as a file rather than left in a code fence for you to copy out. The
  filename is the identity and the extension is the kind, so `.html` renders in a sandboxed frame,
  `.svg` draws, `.md` is typeset and anything else is a source figure with a download. `inline`
  decides where it lands: a card with an **Open** for a page you go and look at, or the thing
  itself drawn in the middle of the paragraph it explains, which is what a flow chart is for.
  Nothing is versioned — the same name replaces — and that is bearable because **`edit` is a
  find-and-replace** that must match exactly once: re-emitting a 40 KB page to change one colour
  is minutes of generation, and it is what has actually been failing against a real endpoint.
- **A panel beside the conversation.** A page she publishes opens it as she finishes writing —
  a page is a thing you look at, and a figure she drew `inline` never opens it, because that one
  is already on screen where she put it. The drawer holds the artifact full size, a **Download**,
  and a bar listing everything published in that chat; the header says how many there are, and
  every card carries its own save control, so something made nine turns ago is reachable without
  scrolling back to the card that made it. An HTML artifact renders in an `iframe` with
  `allow-scripts` and deliberately
  **not** `allow-same-origin`, so a page she wrote has an opaque origin and cannot reach Hera's
  storage — and the API serves an artifact as JSON and a download as an attachment, never as a
  document at Hera's own origin. It can still reach the network, which is written down rather than
  discovered: `sandbox` does not stop a frame loading a font, and a page without one looks broken
  in a way that reads as Hera being broken.
- **She remembers you, and you can read what she remembers.** `hera__remember` stops answering
  "not available in this deployment": what she writes down is one markdown file per memory in
  `~/.hera/memories/`, front matter and prose, the filename as the key — files you can open, edit,
  back up and take somewhere that is not Hera. **Every one that is switched on is in her prompt,
  whole.** There is no retrieval and no ranking, because a memory that was stored and did not
  arrive looks exactly like one that was never stored, and nobody on either side can tell which
  happened. Settings → Memory shows the lot with a **space-left bar**, since injecting everything
  costs room and the ceiling should be something you steer by rather than hit. Switching a memory
  **off keeps the file and gives the space back** — the middle option between having something and
  deleting it. When there is no room she is asked to fold two memories into one rather than
  anything being dropped, and **`hera__forget` does not delete**: it switches a memory off. The
  only thing in Hera that removes one is you, on that screen — where you can also **correct the
  wording** of anything she wrote down, since a memory that is nearly right is more common than
  one that is wrong. **Export MEMORY.md** hands you every memory verbatim, so it can be split
  back into the files it came from.
- **A long argument stops being resent for the rest of the conversation.** A tool call's arguments
  are replayed into every later prompt, so a published page — or a megabyte written to the
  scratchpad — sat underneath every question that followed it, forever. Anything past
  `HERA_CHATS_MAX_HISTORY_ARGUMENT_CHARS` is now cut in the *history* only, with a line saying how
  much is missing. The call went out whole, the event stores it whole, the interface shows it
  whole, and she can read the file back.
- **You can see what she is calling while she is still writing it.** A tool call used to reach the
  browser only once the whole thing had arrived, so a turn spent the entire time it took to write a
  long argument showing nothing at all — and the model's name for the call is in the *first* stream
  fragment. The gutter now draws the row as soon as she names it and fills in what she called it
  with when the arguments land. Streamed and never stored: a call the stream broke off mid-argument
  never ran, and the stored list is the record of what happened.
- **A tool call knows which conversation it is in.** Nothing could, before: her server is built
  once at startup and every call runs in a worker task created when the server connected, so the
  obvious `contextvars` answer reads back *empty* rather than failing. It travels in MCP's `_meta`
  now — never in the arguments, because the model chooses those and would invent a chat id, and a
  `Context` parameter is kept out of the tool's schema entirely so there is nothing to invent.
  `hera__remember(scope="chat")` has been missing exactly this since 0.1.0.
- **One selector, and one popup.** `Select.svelte` replaces every dropdown in the application. The
  trigger is the composer's pill — the shape that was already right — and the popup is the *skill
  picker's*: raised surface, hairline, large radius, the same shadow, a brass check on the chosen
  row. Before this the composer's two pills were a native `<select>` wearing `appearance: none`,
  which gave back the frame and left the list the platform's, and every other selector was bare
  native. A person should not be able to tell from the way a list looks whether it came from a
  dialog, a dropdown or a `⋯` menu — the rail's menus share the frame too. Keyboard throughout:
  arrows walk it, Home and End jump, Escape closes and hands focus back.

### Fixed

- **A long answer could end with “did not answer in time”.** The read timeout was three minutes and
  is now ten, and it is editable on Settings → Models rather than only by hand in `config.toml`. It
  never was a limit on how long an answer may take — it is measured between one piece of the
  response and the next, so what it bounds is *silence*: loading the weights, and working through a
  prompt that has grown a skill body and six rounds of history. Three minutes was not enough for a
  local 35B asked to write a whole page, and what that looked like was a failure under an answer
  that had been going fine.
- **A turn that failed could not be tried again.** *Copy* and *Try again* were drawn by the same
  rule, and that rule required something to copy — so an answer that failed before she had said
  anything offered neither, which is the one message a person is looking at wanting to retry.
  Copy is about the answer and needs one; try again is about the question and does not.
- **A setting you never chose was still recorded, and then outranked its own improvement.**
  `config.toml` is seeded on first run and wins afterwards, which is right — but it was seeded
  with *every* field, so it captured the defaults of whichever version wrote it first and no
  later improvement could reach an existing install. That is why raising the timeout above did
  nothing on a machine that had already run Hera. Values you have not set are no longer written
  down; ones you set still are, and still win.
- **Her own tool names were clipped in the activity gutter.** `scratch write` and `scratch read`
  both came out as `scratch …`, so the two rows a reader most needs to tell apart were the two the
  column made identical.

- **`PATCH /projects/{id}` could not clear a default profile.** The route tested
  `default_profile_id is not None`, which is right for every other field on that body and wrong for
  this one: choosing the screen's empty option was a no-op, and the control snapped back on the
  next load with nothing to explain it.
- **Booting against a database from a newer build crashed with alembic's stack trace.** Checking
  out an older branch — or downgrading Hera — against a `~/.hera` a newer build already migrated
  ended in forty frames and `Can't locate revision identified by '0004'`, at a point where nothing
  connects it to the branch you just switched to. `boot.check_revision` now names the revision,
  names the file it actually looked at, and gives both commands. It refuses rather than repairs:
  stamping the database back leaves columns a later upgrade then fails to add, and downgrading it
  drops data because a shell was in the wrong directory.
- **She spent a whole turn re-running the same search.** Asked for a figure that was not in the
  results, the model ran one identical query four times, exhausted its budget and was cut off
  mid-sentence — every call succeeded, so nothing in the loop noticed. An identical call, same
  tool and same arguments, now runs at most twice in a turn; the third comes back as a result
  saying the words have been tried, quoting what they returned, and to ask differently or answer
  with what it has. Twice rather than once, because the turn cannot know which tools are
  idempotent and reading a file after writing it is the same call with a different answer.
- **Running out of tool calls ends with an answer, not a half-sentence.** The loop used to stop
  the moment the budget was spent, which meant the last batch of results was never shown to the
  model at all — the turn ended on whatever it had said *before* going to look. It now gets one
  final round with the tools withheld, which is the only thing that reliably stops a model asking
  for more. The ceiling rose from 8 rounds to 12, which is affordable now that the budget is not
  being wasted on repeats.
- **A turn could not be read downwards.** Every gutter row was drawn first and all the prose
  after, which is correct only for a turn that does its thinking up front — the moment she
  speaks, thinks again and speaks again, the second thought appeared *above* the sentence that
  prompted it. A turn is one ordered list now: a run of consecutive gutter rows is one block, and
  prose and cards sit between the runs where she put them. Prose written after a tool call no
  longer merges with prose written before it, which was the same bug from the other side.
- **The composer did not block while a card was waiting on you**, though two documents said it
  did — nothing read that field. Sending past an open card wrote a fresh assistant row, and the
  resume routes work from the latest one, so the suspended turn was orphaned and its permission
  card or question could never be answered. `busy` and `blocked` are now separate, because the
  card's own controls must stay live while the composer does not — and because offering **Stop**
  for a turn that already stopped is a lie about what is happening.

### Known gaps

Listed so a missing feature and a forgotten one do not look alike:

- **A skill's bundled files are still unreadable**, and the prompt says otherwise. Every selected
  skill with files beside it arrives with *"read one if this skill tells you to"*, and there is no
  tool that can. `hera__read_resource` is written as a decision
  ([ADR 14](docs/adr/0014-skill-resources-are-readable.md)) and is first in
  [v0.2.1](docs/versions/v0.2.1.md), because it is a sentence in the prompt that is not true.
- **`⌘K` opens Settings** rather than a command palette, and there are no other keyboard shortcuts.
  v0.2.1.
- **The interface is desktop-shaped.** It installs as a PWA and there is no mobile sheet. v0.2.1.
- **Mermaid diagrams are not drawn.** `.mmd` is recognised and says so plainly; an `.svg` artifact
  is a drawn chart today.
- **No dreaming, no sandbox, no agents.** v0.3 — see
  [docs/versions/v0.3.0.md](docs/versions/v0.3.0.md). Settings → Dreaming is listed and disabled,
  because a feature you can see coming is a promise and one you cannot is a surprise.
- **`hera__fetch` and PDFs.** She can find a page and not read it; the composer refuses a PDF.
  Both have their reasoning in [docs/tooling.md](docs/tooling.md).

## [0.1.0] — 2026-08-27

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
